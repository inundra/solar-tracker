"""Importă parcuri.csv și stadii_lunare.csv în baza de date (issue #15).

Folosire:
    python backend/src/importa_csv.py                       # validare/parcuri.csv + validare/stadii_lunare.csv
    python backend/src/importa_csv.py --parcuri validare/exemplu_parcuri.csv --stadii validare/exemplu_stadii_lunare.csv
    python backend/src/importa_csv.py --verifica            # validează și simulează, fără să scrie nimic

Ce face:
- rulează întâi validare/valideaza_csv.py; dacă există erori, nu scrie nimic;
- scrie totul într-o singură tranzacție: ori intră tot, ori nimic;
- e idempotent: parcurile se actualizează după `parc_id`, stadiile după (`parc_id`, `luna`),
  deci rularea repetată nu creează duplicate;
- încarcă poligonul din validare/proiecte_cartate/<parc_id>.geojson, dacă fișierul există;
- nu șterge nimic, decât cu --sterge-lipsa (stadiile din bază care nu mai sunt în CSV, pentru parcurile din CSV).

Formatul fișierelor: validare/schema_csv.md.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from db import REPO, conecteaza

sys.path.insert(0, str(REPO / "validare"))
import valideaza_csv  # noqa: E402  (verificatorul comun cu echipa Setul de adevăr)

COLOANE_PARCURI = [c for c in valideaza_csv.COLOANE_PARCURI if c not in ("lat", "lon", "are_poligon")]
COLOANE_STADII = [c for c in valideaza_csv.COLOANE_STADII if c != "luna"]


@dataclass
class Rezultat:
    fisier: str
    sha256: str
    linii: int = 0
    inserate: int = 0
    actualizate: int = 0
    neschimbate: int = 0
    sterse: int = 0
    avertismente: list[str] = field(default_factory=list)


def citeste_csv(cale: Path) -> list[dict[str, str | None]]:
    """Liniile CSV-ului, cu celulele goale transformate în NULL și coloanele necunoscute ignorate."""
    text = cale.read_text(encoding="utf-8-sig")
    randuri = []
    for rand in csv.DictReader(text.splitlines()):
        curat = {k: (v or "").strip() or None for k, v in rand.items() if k is not None}
        if any(curat.values()):
            randuri.append(curat)
    return randuri


def sha256(cale: Path) -> str:
    return hashlib.sha256(cale.read_bytes()).hexdigest()


def geometrii_geojson(cale: Path) -> list[dict]:
    """Geometriile (Polygon / MultiPolygon) dintr-un FeatureCollection, Feature sau geometrie simplă."""
    obj = json.loads(cale.read_text(encoding="utf-8"))
    if obj.get("type") == "FeatureCollection":
        geoms = [f.get("geometry") for f in obj.get("features", [])]
    elif obj.get("type") == "Feature":
        geoms = [obj.get("geometry")]
    else:
        geoms = [obj]
    geoms = [g for g in geoms if g]
    for g in geoms:
        if g.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"{cale.name}: geometria e {g.get('type')}, aștept Polygon sau MultiPolygon")
    return geoms


SQL_PARC = f"""
INSERT INTO parcuri ({", ".join(COLOANE_PARCURI)}, geom, poligon)
VALUES ({", ".join(f"%({c})s" for c in COLOANE_PARCURI)},
        ST_SetSRID(ST_MakePoint(%(lon)s::float8, %(lat)s::float8), 4326),
        (SELECT ST_Multi(ST_Union(ST_SetSRID(ST_GeomFromGeoJSON(g::text), 4326)))
           FROM jsonb_array_elements(%(poligon)s::jsonb) AS g))
ON CONFLICT (parc_id) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in COLOANE_PARCURI if c != "parc_id")},
    geom = EXCLUDED.geom,
    poligon = EXCLUDED.poligon,
    actualizat_la = now()
WHERE ({", ".join(f"parcuri.{c}" for c in COLOANE_PARCURI)}, parcuri.geom, parcuri.poligon)
      IS DISTINCT FROM ({", ".join(f"EXCLUDED.{c}" for c in COLOANE_PARCURI)}, EXCLUDED.geom, EXCLUDED.poligon)
RETURNING (xmax = 0) AS inserat
"""

SQL_STADIU = f"""
INSERT INTO stadii_adevar ({", ".join(COLOANE_STADII)}, luna)
VALUES ({", ".join(f"%({c})s" for c in COLOANE_STADII)}, to_date(%(luna)s, 'YYYY-MM'))
ON CONFLICT (parc_id, luna) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in COLOANE_STADII if c != "parc_id")},
    actualizat_la = now()
WHERE ({", ".join(f"stadii_adevar.{c}" for c in COLOANE_STADII)})
      IS DISTINCT FROM ({", ".join(f"EXCLUDED.{c}" for c in COLOANE_STADII)})
RETURNING (xmax = 0) AS inserat
"""


def numara(rez: Rezultat, rand) -> None:
    """rand e None când linia exista deja identică (UPDATE-ul a fost sărit)."""
    rez.linii += 1
    if rand is None:
        rez.neschimbate += 1
    elif rand[0]:
        rez.inserate += 1
    else:
        rez.actualizate += 1


def importa_parcuri(conn, cale: Path) -> Rezultat:
    rez = Rezultat(str(cale), sha256(cale))
    dir_poligoane = cale.parent / "proiecte_cartate"
    for r in citeste_csv(cale):
        geo = dir_poligoane / f"{r['parc_id']}.geojson"
        poligon = json.dumps(geometrii_geojson(geo)) if geo.exists() else "[]"
        if r.get("are_poligon") == "da" and not geo.exists():
            rez.avertismente.append(f"{r['parc_id']}: are_poligon=da, dar lipsește {geo.name}; poligonul rămâne gol")
        rand = {c: r.get(c) for c in COLOANE_PARCURI} | {"lat": r["lat"], "lon": r["lon"], "poligon": poligon}
        numara(rez, conn.execute(SQL_PARC, rand).fetchone())

    # Punctul din CSV ar trebui să cadă în (sau lângă) poligon; altfel e probabil o greșeală de coordonate.
    for (pid, dist) in conn.execute(
        "SELECT parc_id, round(ST_Distance(geom::geography, poligon::geography)) FROM parcuri"
        " WHERE poligon IS NOT NULL AND NOT ST_DWithin(geom::geography, poligon::geography, 500)"
    ):
        rez.avertismente.append(f"{pid}: punctul lat/lon e la {dist} m de poligon")
    return rez


def importa_stadii(conn, cale: Path, sterge_lipsa: bool) -> Rezultat:
    rez = Rezultat(str(cale), sha256(cale))
    randuri = citeste_csv(cale)
    for r in randuri:
        numara(rez, conn.execute(SQL_STADIU, {c: r.get(c) for c in COLOANE_STADII} | {"luna": r["luna"]}).fetchone())

    chei = [(r["parc_id"], r["luna"]) for r in randuri]
    parcuri = sorted({pid for pid, _ in chei})
    lipsa = conn.execute(
        "SELECT parc_id, to_char(luna, 'YYYY-MM') FROM stadii_adevar WHERE parc_id = ANY(%s)"
        " AND (parc_id, to_char(luna, 'YYYY-MM')) NOT IN (SELECT * FROM unnest(%s::text[], %s::text[]))"
        " ORDER BY 1, 2",
        (parcuri, [c[0] for c in chei], [c[1] for c in chei]),
    ).fetchall()
    if lipsa and sterge_lipsa:
        for pid, luna in lipsa:
            conn.execute("DELETE FROM stadii_adevar WHERE parc_id = %s AND luna = to_date(%s, 'YYYY-MM')", (pid, luna))
        rez.sterse = len(lipsa)
    elif lipsa:
        rez.avertismente.append(
            f"{len(lipsa)} stadii sunt în bază, dar nu în CSV (ex. {lipsa[0][0]} {lipsa[0][1]});"
            " rulați cu --sterge-lipsa ca să le ștergeți"
        )
    return rez


def noteaza(conn, rez: Rezultat) -> None:
    conn.execute(
        "INSERT INTO importuri (fisier, sha256, linii, inserate, actualizate, neschimbate, sterse)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (rez.fisier, rez.sha256, rez.linii, rez.inserate, rez.actualizate, rez.neschimbate, rez.sterse),
    )


def valideaza(parcuri: Path, stadii: Path | None) -> bool:
    raport = valideaza_csv.Raport()
    ids = valideaza_csv.verifica_parcuri(parcuri, raport)
    if stadii:
        valideaza_csv.verifica_stadii(stadii, raport, ids)
    for a in raport.avertismente:
        print(f"AVERTISMENT {a}")
    for e in raport.erori:
        print(f"EROARE      {e}")
    if raport.erori:
        print(f"\n{len(raport.erori)} erori: nu am importat nimic. Corectați fișierele și rulați din nou.")
        return False
    return True


def importa(conn, parcuri: Path, stadii: Path | None, sterge_lipsa: bool = False, verifica: bool = False) -> list[Rezultat]:
    """Validează și importă într-o singură tranzacție. Cu verifica=True, tranzacția se anulează la final."""
    if not valideaza(parcuri, stadii):
        raise SystemExit(1)

    class Simulare(Exception):
        pass

    rezultate: list[Rezultat] = []
    try:
        with conn.transaction():
            rezultate.append(importa_parcuri(conn, parcuri))
            if stadii:
                rezultate.append(importa_stadii(conn, stadii, sterge_lipsa))
            for rez in rezultate:
                noteaza(conn, rez)
            if verifica:
                raise Simulare
    except Simulare:
        pass
    return rezultate


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--parcuri", type=Path, default=REPO / "validare" / "parcuri.csv")
    p.add_argument("--stadii", type=Path, default=REPO / "validare" / "stadii_lunare.csv",
                   help="fișierul cu stadii lunare (sărit dacă nu există)")
    p.add_argument("--dsn", help="adresa bazei (altfel DATABASE_URL)")
    p.add_argument("--sterge-lipsa", action="store_true",
                   help="șterge stadiile din bază care nu mai apar în CSV (doar pentru parcurile din CSV)")
    p.add_argument("--verifica", action="store_true", help="simulează importul și anulează la final")
    args = p.parse_args(argv)

    if not args.parcuri.exists():
        print(f"Nu găsesc {args.parcuri}")
        return 1
    stadii = args.stadii if args.stadii.exists() else None
    if stadii is None:
        print(f"(nu găsesc {args.stadii}; import doar parcurile)")

    with conecteaza(args.dsn) as conn:
        rezultate = importa(conn, args.parcuri, stadii, args.sterge_lipsa, args.verifica)
        total = conn.execute("SELECT count(*) FROM parcuri").fetchone()[0]

    for rez in rezultate:
        for a in rez.avertismente:
            print(f"AVERTISMENT {a}")
        sterse = f", {rez.sterse} șterse" if rez.sterse else ""
        print(f"{Path(rez.fisier).name}: {rez.linii} linii, {rez.inserate} noi, {rez.actualizate} actualizate, {rez.neschimbate} neschimbate{sterse}")
    if args.verifica:
        print("Simulare: nimic nu a fost scris în bază.")
    else:
        print(f"OK: {total} parcuri în bază.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
