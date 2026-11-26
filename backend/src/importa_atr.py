"""Importă lista de ATR-uri (avize tehnice de racordare) în tabelele `atr` și `companii`.

Folosire:
    python backend/src/importa_atr.py backend/date_brute/atr_guvern_2026.csv
    python backend/src/importa_atr.py fisier.csv --sursa "gov.ro, lista titularilor ATR, mai 2026"
    python backend/src/importa_atr.py fisier.csv --verifica      # validează și simulează, fără să scrie

CSV-ul (formatul e în backend/schema.md, secțiunea „atr”) se obține din PDF-ul Guvernului cu
`extrage_atr_pdf.py`, sau se completează de mână. Coloane: numar_atr, data_atr, titular, cui, judet, mw,
operator, etapa, data_pif, tehnologie, localitate, sursa, note. Obligatorii: numar_atr, titular, judet, mw.

- Județul poate fi cod („DJ”) sau nume („Dolj”, „DOLJ”). MW acceptă virgulă zecimală. Datele: 2023-05-17 sau 17.05.2023.
- Fără `tehnologie`, o ghicim din numele titularului (solar/PV → fotovoltaic, BESS/storage → stocare).
- La orice eroare nu scrie nimic. Rularea repetată nu face duplicate: cheia e (numar_atr, titular, judet).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import comun
from db import conecteaza

COLOANE = ["numar_atr", "data_atr", "titular", "cui", "judet", "mw", "operator", "etapa", "data_pif",
           "tehnologie", "localitate", "sursa", "note"]
OBLIGATORII = ["numar_atr", "titular", "judet", "mw"]
TEHNOLOGII = {"fotovoltaic", "stocare", "hibrid", "eolian", "alta", "necunoscuta"}

_INDICII = [
    ("stocare", r"\b(bess|storage|stocare|battery|baterii)\b"),
    ("eolian", r"\b(wind|eolian\w*|vant)\b"),
    ("fotovoltaic", r"\b(solar\w*|pv|photovoltaic|fotovoltaic\w*|sun\w*)\b"),
]


def ghiceste_tehnologia(titular: str) -> str:
    n = comun.fara_diacritice(titular)
    gasite = [t for t, rx in _INDICII if re.search(rx, n)]
    if "stocare" in gasite and "fotovoltaic" in gasite:
        return "hibrid"
    return gasite[0] if gasite else "necunoscuta"


@dataclass
class Rezultat:
    fisier: str
    sha256: str
    linii: int = 0
    inserate: int = 0
    actualizate: int = 0
    neschimbate: int = 0
    erori: list[str] = field(default_factory=list)
    avertismente: list[str] = field(default_factory=list)


def pregateste(randuri: list[dict], sursa_implicita: str | None, rez: Rezultat) -> list[dict]:
    """Transformă liniile CSV în valori pentru bază; erorile se adună în rez.erori."""
    curate, chei = [], {}
    for nr, r in enumerate(randuri, start=2):
        lipsa = [c for c in OBLIGATORII if not r.get(c)]
        if lipsa:
            rez.erori.append(f"linia {nr}: lipsesc {', '.join(lipsa)}")
            continue
        try:
            judet = comun.cod_judet(r["judet"])
            if not judet:
                raise ValueError(f"județul „{r['judet']}” nu e cunoscut")
            mw = comun.numar(r["mw"])
            if mw is None or mw < 0:
                raise ValueError(f"MW „{r['mw']}” nu e un număr pozitiv")
            cui = comun.cui(r.get("cui"))
            if cui and not re.fullmatch(r"[0-9]{2,10}", cui):
                raise ValueError(f"CUI „{r['cui']}” nu are 2–10 cifre")
            tehnologie = (r.get("tehnologie") or "").lower() or ghiceste_tehnologia(r["titular"])
            if tehnologie not in TEHNOLOGII:
                raise ValueError(f"tehnologia „{tehnologie}” nu e una din {sorted(TEHNOLOGII)}")
            sursa = r.get("sursa") or sursa_implicita
            if not sursa:
                raise ValueError("lipsește sursa (coloana `sursa` sau opțiunea --sursa)")
            v = {
                "numar": r["numar_atr"], "data_atr": comun.data(r.get("data_atr")),
                "titular": re.sub(r"\s+", " ", r["titular"]).strip(), "cui": cui, "judet": judet, "mw": mw,
                "operator": r.get("operator"), "etapa": r.get("etapa"), "data_pif": comun.data(r.get("data_pif")),
                "tehnologie": tehnologie, "localitate": r.get("localitate"), "sursa": sursa, "note": r.get("note"),
            }
        except ValueError as e:
            rez.erori.append(f"linia {nr}: {e}")
            continue
        cheie = (v["numar"], v["titular"], v["judet"])
        if cheie in chei:
            rez.erori.append(f"linia {nr}: același ATR ca la linia {chei[cheie]} ({v['numar']}, {v['titular']})")
            continue
        chei[cheie] = nr
        curate.append(v)
    return curate


CAMPURI = ["numar", "data_atr", "titular", "cui", "judet", "mw", "operator", "etapa", "data_pif",
           "tehnologie", "localitate", "sursa", "note"]

SQL_ATR = f"""
INSERT INTO atr ({", ".join(CAMPURI)})
VALUES ({", ".join(f"%({c})s" for c in CAMPURI)})
ON CONFLICT (numar, titular, judet) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in CAMPURI if c not in ("numar", "titular", "judet"))},
    actualizat_la = now()
WHERE ({", ".join(f"atr.{c}" for c in CAMPURI)}) IS DISTINCT FROM ({", ".join(f"EXCLUDED.{c}" for c in CAMPURI)})
RETURNING (xmax = 0) AS inserat
"""

SQL_COMPANIE = """
INSERT INTO companii (cui, nume) VALUES (%s, %s)
ON CONFLICT (cui) DO UPDATE SET nume = EXCLUDED.nume, actualizat_la = now()
WHERE companii.nume IS DISTINCT FROM EXCLUDED.nume
"""


def importa(conn, cale: Path, sursa: str | None = None, verifica: bool = False) -> Rezultat:
    rez = Rezultat(str(cale), comun.sha256(cale))
    randuri = comun.citeste_csv(cale)
    necunoscute = sorted(set().union(*(r.keys() for r in randuri)) - set(COLOANE)) if randuri else []
    if necunoscute:
        rez.avertismente.append(f"coloane ignorate: {', '.join(necunoscute)}")
    valori = pregateste(randuri, sursa, rez)
    if rez.erori:
        return rez

    class Simulare(Exception):
        pass

    try:
        with conn.transaction():
            for v in valori:
                if v["cui"]:
                    conn.execute(SQL_COMPANIE, (v["cui"], v["titular"]))
                rand = conn.execute(SQL_ATR, v).fetchone()
                rez.linii += 1
                if rand is None:
                    rez.neschimbate += 1
                elif rand[0]:
                    rez.inserate += 1
                else:
                    rez.actualizate += 1
            comun.noteaza_import(conn, rez.fisier, rez.sha256, rez.linii, rez.inserate, rez.actualizate, rez.neschimbate)
            if verifica:
                raise Simulare
    except Simulare:
        pass
    return rez


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", type=Path)
    p.add_argument("--sursa", help="sursa pentru liniile fără coloana `sursa` (ex. URL-ul PDF-ului)")
    p.add_argument("--dsn", help="adresa bazei (altfel DATABASE_URL)")
    p.add_argument("--verifica", action="store_true", help="simulează importul și anulează la final")
    args = p.parse_args(argv)
    if not args.csv.exists():
        print(f"Nu găsesc {args.csv}")
        return 1
    with conecteaza(args.dsn) as conn:
        rez = importa(conn, args.csv, args.sursa, args.verifica)
        total, mw = conn.execute("SELECT count(*), coalesce(sum(mw), 0) FROM atr").fetchone()
    for a in rez.avertismente:
        print(f"AVERTISMENT {a}")
    for e in rez.erori:
        print(f"EROARE      {e}")
    if rez.erori:
        print(f"\n{len(rez.erori)} erori: nu am importat nimic.")
        return 1
    print(f"{args.csv.name}: {rez.linii} linii, {rez.inserate} noi, {rez.actualizate} actualizate, {rez.neschimbate} neschimbate")
    print("Simulare: nimic nu a fost scris în bază." if args.verifica else f"OK: {total} ATR-uri în bază, {mw:.0f} MW.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
