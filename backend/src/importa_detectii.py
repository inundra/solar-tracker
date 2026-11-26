"""Importă detecțiile (parcuri și șantiere găsite pe imagini) și jurnalul lor de dovezi.

Folosire:
    python backend/src/importa_detectii.py pipeline/iesiri/detectii_DJ_GJ.geojson
    python backend/src/importa_detectii.py tzsam_romania.geojson --sursa tz-sam
    python backend/src/importa_detectii.py fisier.geojson --verifica     # validează și simulează

Intrarea e un GeoJSON FeatureCollection, un Feature pe detecție (contractul cu Pipeline Satelitar e în
backend/schema.md, secțiunea „Contract: detecții de la pipeline”). Pe scurt, în `properties`:
    detectie_id      obligatoriu, stabil între rulări (ex. „DJ-2026-0007”)
    stadiu_curent    obligatoriu: teren_gol | santier | panouri | gata | nesigur
    sursa            pipeline | tz-sam | osm | manual (sau --sursa)
    judet, uat, tip, data_stadiu, data_defrisare, data_module, incredere,
    mwp_estimat, mwp_min, mwp_max, parc_id, versiune_pipeline    opționale
    jurnal           opțional: listă de {data_imagine, stadiu, sursa_imagine, id_imagine, tile, cer_senin, suprafata_ha, note}

Ce face în plus:
- județul lipsă se ia din conturul județelor (dacă e încărcat cu importa_judete.py);
- `parc_id` lipsă se completează dacă detecția se suprapune cu un parc din setul de adevăr;
- `data_defrisare` / `data_module` lipsă se iau din jurnal (prima imagine cu șantier / cu panouri);
- marchează duplicatele: același parc din două surse (suprapunere IoU ≥ 0,3) se numără o singură dată,
  cu prioritatea manual > pipeline > tz-sam > osm.
La orice eroare nu scrie nimic. Rularea repetată actualizează, fără duplicate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

import comun
from db import conecteaza

SURSE = ("manual", "pipeline", "tz-sam", "osm")        # în ordinea priorității
STADII = {"teren_gol", "santier", "panouri", "gata", "nesigur"}
SURSE_IMAGINE = {"sentinel-2", "sentinel-1", "google-earth", "planet", "ortofoto", "alta"}
TIPURI = {"fotovoltaic", "stocare", "necunoscut"}
ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
PRAG_IOU_DUPLICAT = 0.3


@dataclass
class Rezultat:
    fisier: str
    sha256: str
    linii: int = 0
    inserate: int = 0
    actualizate: int = 0
    neschimbate: int = 0
    jurnal: int = 0
    duplicate: int = 0
    legate_de_parcuri: int = 0
    erori: list[str] = field(default_factory=list)
    avertismente: list[str] = field(default_factory=list)


def _zecimal(props: dict, cheie: str, mn: float | None = None, mx: float | None = None) -> float | None:
    v = props.get(cheie)
    if v in (None, ""):
        return None
    v = comun.numar(str(v))
    if (mn is not None and v < mn) or (mx is not None and v > mx):
        raise ValueError(f"{cheie}={v} e în afara intervalului [{mn}, {mx}]")
    return v


def pregateste(features: list[dict], sursa_implicita: str | None, rez: Rezultat) -> list[dict]:
    curate, vazute = [], set()
    for i, f in enumerate(features, start=1):
        props = f.get("properties") or {}
        eticheta = f"detecția {i} ({props.get('detectie_id', 'fără id')})"
        try:
            did = str(props.get("detectie_id") or "").strip()
            if not ID.match(did):
                raise ValueError("detectie_id lipsește sau are caractere nepermise (litere, cifre, _ . : -)")
            if did in vazute:
                raise ValueError("detectie_id apare de două ori în fișier")
            vazute.add(did)
            geom = f.get("geometry") or {}
            if geom.get("type") not in ("Polygon", "MultiPolygon"):
                raise ValueError(f"geometria e {geom.get('type')}, aștept Polygon sau MultiPolygon")
            sursa = props.get("sursa") or sursa_implicita
            if sursa not in SURSE:
                raise ValueError(f"sursa „{sursa}” nu e una din {', '.join(SURSE)}")
            stadiu = props.get("stadiu_curent")
            if stadiu not in STADII:
                raise ValueError(f"stadiu_curent „{stadiu}” nu e unul din {sorted(STADII)}")
            tip = props.get("tip") or "fotovoltaic"
            if tip not in TIPURI:
                raise ValueError(f"tip „{tip}” nu e unul din {sorted(TIPURI)}")
            judet = None
            if props.get("judet"):
                judet = comun.cod_judet(str(props["judet"]))
                if not judet:
                    raise ValueError(f"județul „{props['judet']}” nu e cunoscut")
            jurnal = []
            for j, intrare in enumerate(props.get("jurnal") or [], start=1):
                if intrare.get("stadiu") not in STADII:
                    raise ValueError(f"jurnal[{j}]: stadiul „{intrare.get('stadiu')}” nu e permis")
                if intrare.get("sursa_imagine") not in SURSE_IMAGINE:
                    raise ValueError(f"jurnal[{j}]: sursa_imagine „{intrare.get('sursa_imagine')}” nu e permisă")
                if not intrare.get("id_imagine") or not intrare.get("data_imagine"):
                    raise ValueError(f"jurnal[{j}]: lipsesc data_imagine sau id_imagine")
                jurnal.append({
                    "data_imagine": comun.data(str(intrare["data_imagine"])), "stadiu": intrare["stadiu"],
                    "sursa_imagine": intrare["sursa_imagine"], "id_imagine": str(intrare["id_imagine"]),
                    "tile": intrare.get("tile"), "cer_senin": _zecimal(intrare, "cer_senin", 0, 1),
                    "suprafata_ha": _zecimal(intrare, "suprafata_ha", 0), "note": intrare.get("note"),
                })
            v = {
                "detectie_id": did, "sursa": sursa, "judet": judet, "uat": props.get("uat"), "tip": tip,
                "geom": json.dumps(geom), "stadiu_curent": stadiu,
                "data_stadiu": comun.data(props.get("data_stadiu")),
                "data_defrisare": comun.data(props.get("data_defrisare")),
                "data_module": comun.data(props.get("data_module")),
                "incredere": _zecimal(props, "incredere", 0, 1),
                "mwp_estimat": _zecimal(props, "mwp_estimat", 0), "mwp_min": _zecimal(props, "mwp_min", 0),
                "mwp_max": _zecimal(props, "mwp_max", 0), "parc_id": props.get("parc_id"),
                "versiune_pipeline": props.get("versiune_pipeline"), "jurnal": jurnal,
            }
            if v["mwp_min"] is not None and v["mwp_max"] is not None and v["mwp_min"] > v["mwp_max"]:
                raise ValueError("mwp_min > mwp_max")
            completeaza_date_din_jurnal(v)
            if v["data_defrisare"] and v["data_module"] and v["data_defrisare"] > v["data_module"]:
                raise ValueError("data_defrisare e după data_module")
            curate.append(v)
        except (ValueError, TypeError) as e:
            rez.erori.append(f"{eticheta}: {e}")
    return curate


def completeaza_date_din_jurnal(v: dict) -> None:
    """Datele lipsă se iau din jurnal: prima imagine cu șantier sau mai mult (defrișare), prima cu panouri
    și ultima imagine decisivă (data stadiului curent)."""
    j = v["jurnal"]
    def prima(stadii):
        return min((x["data_imagine"] for x in j if x["stadiu"] in stadii), default=None)
    v["data_defrisare"] = v["data_defrisare"] or prima({"santier", "panouri", "gata"})
    v["data_module"] = v["data_module"] or prima({"panouri", "gata"})
    v["data_stadiu"] = v["data_stadiu"] or max((x["data_imagine"] for x in j if x["stadiu"] != "nesigur"), default=None)


SQL_DETECTIE = """
WITH g AS (SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(
                ST_SetSRID(ST_GeomFromGeoJSON(%(geom)s), 4326)), 3)) AS poligon)
INSERT INTO detectii (detectie_id, sursa, judet, uat, poligon, tip, stadiu_curent, data_stadiu, data_defrisare,
                      data_module, incredere, mwp_estimat, mwp_min, mwp_max, parc_id, versiune_pipeline)
SELECT %(detectie_id)s, %(sursa)s,
       coalesce(%(judet)s, (SELECT j.cod FROM judete j WHERE ST_Intersects(j.contur, ST_PointOnSurface(g.poligon)) LIMIT 1)),
       %(uat)s, g.poligon, %(tip)s, %(stadiu_curent)s, %(data_stadiu)s, %(data_defrisare)s, %(data_module)s,
       %(incredere)s, %(mwp_estimat)s, %(mwp_min)s, %(mwp_max)s,
       coalesce(%(parc_id)s, (SELECT p.parc_id FROM parcuri p
                              WHERE ST_Intersects(coalesce(p.poligon, p.geom), g.poligon)
                              ORDER BY ST_Area(ST_Intersection(coalesce(p.poligon, ST_Buffer(p.geom, 0.0001)), g.poligon)) DESC
                              LIMIT 1)),
       %(versiune_pipeline)s
FROM g
ON CONFLICT (detectie_id) DO UPDATE SET
    sursa = EXCLUDED.sursa, judet = EXCLUDED.judet, uat = EXCLUDED.uat, poligon = EXCLUDED.poligon,
    tip = EXCLUDED.tip, stadiu_curent = EXCLUDED.stadiu_curent, data_stadiu = EXCLUDED.data_stadiu,
    data_defrisare = EXCLUDED.data_defrisare, data_module = EXCLUDED.data_module, incredere = EXCLUDED.incredere,
    mwp_estimat = EXCLUDED.mwp_estimat, mwp_min = EXCLUDED.mwp_min, mwp_max = EXCLUDED.mwp_max,
    parc_id = EXCLUDED.parc_id, versiune_pipeline = EXCLUDED.versiune_pipeline, actualizat_la = now()
WHERE (detectii.sursa, detectii.judet, detectii.uat, detectii.poligon, detectii.tip, detectii.stadiu_curent,
       detectii.data_stadiu, detectii.data_defrisare, detectii.data_module, detectii.incredere, detectii.mwp_estimat,
       detectii.mwp_min, detectii.mwp_max, detectii.parc_id, detectii.versiune_pipeline)
      IS DISTINCT FROM
      (EXCLUDED.sursa, EXCLUDED.judet, EXCLUDED.uat, EXCLUDED.poligon, EXCLUDED.tip, EXCLUDED.stadiu_curent,
       EXCLUDED.data_stadiu, EXCLUDED.data_defrisare, EXCLUDED.data_module, EXCLUDED.incredere, EXCLUDED.mwp_estimat,
       EXCLUDED.mwp_min, EXCLUDED.mwp_max, EXCLUDED.parc_id, EXCLUDED.versiune_pipeline)
RETURNING (xmax = 0) AS inserat
"""

SQL_JURNAL = """
INSERT INTO jurnal_detectii (detectie_id, data_imagine, stadiu, sursa_imagine, id_imagine, tile, cer_senin,
                             suprafata_ha, versiune_pipeline, note)
VALUES (%(detectie_id)s, %(data_imagine)s, %(stadiu)s, %(sursa_imagine)s, %(id_imagine)s, %(tile)s, %(cer_senin)s,
        %(suprafata_ha)s, %(versiune_pipeline)s, %(note)s)
ON CONFLICT (detectie_id, sursa_imagine, id_imagine, versiune_pipeline) DO UPDATE SET
    data_imagine = EXCLUDED.data_imagine, stadiu = EXCLUDED.stadiu, tile = EXCLUDED.tile,
    cer_senin = EXCLUDED.cer_senin, suprafata_ha = EXCLUDED.suprafata_ha, note = EXCLUDED.note
"""

# Recalculează duplicatele pe toată baza: o detecție e duplicat dacă se suprapune (IoU ≥ prag) cu una dintr-o
# sursă diferită, cu prioritate mai mare. Așa importurile pot veni în orice ordine.
SQL_DUPLICATE = """
WITH prioritate AS (SELECT * FROM unnest(%(surse)s::text[]) WITH ORDINALITY AS t(sursa, rang)),
d AS (SELECT d.detectie_id, d.sursa, d.poligon, p.rang FROM detectii d JOIN prioritate p USING (sursa)),
perechi AS (
    SELECT a.detectie_id,
           (SELECT b.detectie_id FROM d b
             WHERE b.sursa <> a.sursa AND b.rang < a.rang AND ST_Intersects(a.poligon, b.poligon)
               AND ST_Area(ST_Intersection(a.poligon, b.poligon)) / nullif(ST_Area(ST_Union(a.poligon, b.poligon)), 0)
                   >= %(prag)s
             ORDER BY b.rang, ST_Area(ST_Intersection(a.poligon, b.poligon)) DESC LIMIT 1) AS original
    FROM d a
)
UPDATE detectii x SET duplicat_al = perechi.original
FROM perechi
WHERE x.detectie_id = perechi.detectie_id AND x.duplicat_al IS DISTINCT FROM perechi.original
"""


def importa(conn, cale: Path, sursa: str | None = None, verifica: bool = False) -> Rezultat:
    rez = Rezultat(str(cale), comun.sha256(cale))
    obj = json.loads(cale.read_text(encoding="utf-8"))
    features = obj.get("features", []) if obj.get("type") == "FeatureCollection" else [obj]
    valori = pregateste(features, sursa, rez)
    if rez.erori:
        return rez

    class Simulare(Exception):
        pass

    try:
        with conn.transaction():
            for v in valori:
                rand = conn.execute(SQL_DETECTIE, v).fetchone()
                rez.linii += 1
                if rand is None:
                    rez.neschimbate += 1
                elif rand[0]:
                    rez.inserate += 1
                else:
                    rez.actualizate += 1
                for j in v["jurnal"]:
                    conn.execute(SQL_JURNAL, j | {"detectie_id": v["detectie_id"],
                                                  "versiune_pipeline": v["versiune_pipeline"] or ""})
                    rez.jurnal += 1
            ids = [v["detectie_id"] for v in valori]
            fara_judet = conn.execute(
                "SELECT detectie_id FROM detectii WHERE detectie_id = ANY(%s) AND judet IS NULL", (ids,)).fetchall()
            if fara_judet:
                raise ValueError(f"{len(fara_judet)} detecții fără județ (ex. {fara_judet[0][0]}): puneți `judet` în"
                                 " properties sau încărcați conturul județelor cu importa_judete.py")
            conn.execute(SQL_DUPLICATE, {"surse": list(SURSE), "prag": PRAG_IOU_DUPLICAT})
            rez.duplicate = conn.execute(
                "SELECT count(*) FROM detectii WHERE detectie_id = ANY(%s) AND duplicat_al IS NOT NULL", (ids,)).fetchone()[0]
            rez.legate_de_parcuri = conn.execute(
                "SELECT count(*) FROM detectii WHERE detectie_id = ANY(%s) AND parc_id IS NOT NULL", (ids,)).fetchone()[0]
            comun.noteaza_import(conn, rez.fisier, rez.sha256, rez.linii, rez.inserate, rez.actualizate, rez.neschimbate)
            if verifica:
                raise Simulare
    except Simulare:
        pass
    except psycopg.errors.NotNullViolation as e:
        if "judet" not in str(e):
            raise
        rez.erori.append("o detecție nu are județ: puneți `judet` în properties sau încărcați conturul"
                         " județelor cu importa_judete.py")
    except ValueError as e:
        rez.erori.append(str(e))
    return rez


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("geojson", type=Path)
    p.add_argument("--sursa", choices=SURSE, help="sursa pentru detecțiile fără `sursa` în properties")
    p.add_argument("--dsn", help="adresa bazei (altfel DATABASE_URL)")
    p.add_argument("--verifica", action="store_true", help="simulează importul și anulează la final")
    args = p.parse_args(argv)
    if not args.geojson.exists():
        print(f"Nu găsesc {args.geojson}")
        return 1
    # Cu `with conecteaza(...)`, psycopg face commit la ieșire; erorile au anulat deja tranzacția importului.
    with conecteaza(args.dsn) as conn:
        rez = importa(conn, args.geojson, args.sursa, args.verifica)
    for a in rez.avertismente:
        print(f"AVERTISMENT {a}")
    for e in rez.erori:
        print(f"EROARE      {e}")
    if rez.erori:
        print(f"\n{len(rez.erori)} erori: nu am importat nimic.")
        return 1
    print(f"{args.geojson.name}: {rez.linii} detecții ({rez.inserate} noi, {rez.actualizate} actualizate,"
          f" {rez.neschimbate} neschimbate), {rez.jurnal} intrări în jurnal, {rez.duplicate} duplicate,"
          f" {rez.legate_de_parcuri} legate de parcuri din setul de adevăr")
    if args.verifica:
        print("Simulare: nimic nu a fost scris în bază.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
