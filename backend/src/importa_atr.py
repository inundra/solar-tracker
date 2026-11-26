"""Importă lista de ATR-uri (avize tehnice de racordare) în tabelele `atr` și `companii`.

Folosire:
    python backend/src/importa_atr.py backend/date_brute/atr_guvern_2026.csv
    python backend/src/importa_atr.py fisier.csv --sursa "gov.ro, lista titularilor ATR, mai 2026"
    python backend/src/importa_atr.py fisier.csv --verifica      # validează și simulează, fără să scrie

CSV-ul (formatul e în backend/schema.md, secțiunea „atr”) se obține din PDF-ul Guvernului cu
`extrage_atr_pdf.py`, sau se completează de mână. Coloane: numar_atr, data_atr, titular, cui, judet, mw,
operator, etapa, data_pif, tehnologie, localitate, sursa, note. Obligatorii: numar_atr, titular, judet, mw.

Lista reală are celule murdare, așa că importul e tolerant:
- județul: cod, nume, nume cu greșeli („Dambovta”, „BISTRITA NASAU”), reședința („Timisoara”) sau mai multe
  județe („Arad si Timis”: primul în `judet`, restul în `judete_secundare`);
- CUI-ul: prefixe și resturi din coloana vecină („L. 45427207”, „SRL21566895”) se curăță, cu avertisment;
- PIF-ul: textul original rămâne în `pif_text`; din el se scot starea (estimat / realizat / anulat /
  retehnologizat), data și anul („PIF estimat la 31.12.2027”, „Pif estimat 2033”, „PIF/11.04.2012”);
- liniile fără număr ATR primesc un număr stabil „fara-numar-<hash>”;
- liniile care nu pot fi reparate (MW ilizibil, județ necunoscut) se sar și se scriu în
  `<fișier>_respinse.csv`, cu motivul, ca să le corectați de mână. Restul se importă.
Cu --strict, orice problemă oprește tot importul (nimic nu se scrie).
Fără `tehnologie`, o ghicim din numele titularului (solar/PV → fotovoltaic, BESS/storage → stocare).
Rularea repetată nu face duplicate: cheia e (numar_atr, titular, judet).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
    reparate: int = 0
    erori: list[str] = field(default_factory=list)          # opresc importul (fișier invalid sau --strict)
    avertismente: list[str] = field(default_factory=list)
    respinse: list[dict] = field(default_factory=list)      # linii sărite: {"linia", "motiv", ...coloanele CSV}


def _numar_stabil(r: dict) -> str:
    cheie = "|".join(comun.fara_diacritice(r.get(c) or "") for c in ("titular", "judet", "mw", "data_atr"))
    return "fara-numar-" + hashlib.sha1(cheie.encode()).hexdigest()[:8]


def pregateste(randuri: list[dict], sursa_implicita: str | None, rez: Rezultat) -> list[dict]:
    """Transformă liniile CSV în valori pentru bază. Liniile nereparabile ajung în rez.respinse,
    corecturile în rez.avertismente."""
    curate, chei = [], {}

    def respinge(nr: int, r: dict, motiv: str) -> None:
        rez.respinse.append({"linia": nr, "motiv": motiv} | r)

    for nr, r in enumerate(randuri, start=2):
        lipsa = [c for c in ("titular", "judet", "mw") if not r.get(c)]
        if lipsa:
            respinge(nr, r, f"lipsesc {', '.join(lipsa)}")
            continue
        note, reparat = [r["note"]] if r.get("note") else [], False

        judete = comun.judete_din_text(r["judet"])
        if not judete:
            respinge(nr, r, f"județul „{r['judet']}” nu e cunoscut")
            continue
        if comun.cod_judet(r["judet"]) != judete[0] or len(judete) > 1:
            rez.avertismente.append(f"linia {nr}: județ „{r['judet']}” → {', '.join(judete)}")
        if len(judete) > 1:
            note.append(f"ATR pe mai multe județe: {', '.join(judete)}")

        mw, mw_reparat = comun.mw_tolerant(r["mw"])
        if mw is None or mw < 0:
            respinge(nr, r, f"MW „{r['mw']}” nu se poate citi")
            continue
        if mw_reparat:
            reparat = True
            note.append(f"MW citit din „{r['mw']}”")
            rez.avertismente.append(f"linia {nr}: MW „{r['mw']}” → {mw}")

        cui, cui_reparat = comun.cui_tolerant(r.get("cui"))
        if cui_reparat:
            reparat = True
            note.append(f"CUI citit din „{r['cui']}”" if cui else f"CUI ilizibil: „{r['cui']}”")
            rez.avertismente.append(f"linia {nr}: CUI „{r['cui']}” → {cui or 'gol'}")

        numar = r.get("numar_atr")
        if not numar:
            numar = _numar_stabil(r)
            note.append("fără număr ATR în listă")
            rez.avertismente.append(f"linia {nr}: lipsește numărul ATR, folosesc {numar}")

        try:
            data_atr = comun.data(r.get("data_atr"))
        except ValueError:
            data_atr = None
            note.append(f"data ATR ilizibilă: „{r['data_atr']}”")
            rez.avertismente.append(f"linia {nr}: data ATR „{r['data_atr']}” nu se poate citi, o las goală")

        stare_pif, data_pif, an_pif = comun.pif(r.get("data_pif"))

        tehnologie = (r.get("tehnologie") or "").lower() or ghiceste_tehnologia(r["titular"])
        if tehnologie not in TEHNOLOGII:
            respinge(nr, r, f"tehnologia „{tehnologie}” nu e una din {sorted(TEHNOLOGII)}")
            continue
        sursa = r.get("sursa") or sursa_implicita
        if not sursa:
            rez.erori.append("lipsește sursa (coloana `sursa` sau opțiunea --sursa)")
            return []

        v = {
            "numar": numar, "data_atr": data_atr,
            "titular": re.sub(r"\s+", " ", r["titular"]).strip(), "cui": cui, "judet": judete[0],
            "judete_secundare": judete[1:], "mw": mw, "operator": r.get("operator"), "etapa": r.get("etapa"),
            "data_pif": data_pif, "pif_text": r.get("data_pif"), "stare_pif": stare_pif, "an_pif": an_pif,
            "tehnologie": tehnologie, "localitate": r.get("localitate"), "sursa": sursa,
            "note": "; ".join(note) or None, "reparat": reparat,
        }
        cheie = (v["numar"], v["titular"], v["judet"])
        if cheie in chei:
            respinge(nr, r, f"același ATR ca la linia {chei[cheie]} ({v['numar']}, {v['titular']})")
            continue
        chei[cheie] = nr
        rez.reparate += reparat
        curate.append(v)
    return curate


CAMPURI = ["numar", "data_atr", "titular", "cui", "judet", "judete_secundare", "mw", "operator", "etapa", "data_pif",
           "pif_text", "stare_pif", "an_pif", "tehnologie", "localitate", "sursa", "note", "reparat"]

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


def scrie_respinse(rez: Rezultat, cale: Path) -> Path | None:
    """Liniile sărite, cu motivul, într-un CSV lângă fișierul importat (pentru corectat de mână)."""
    if not rez.respinse:
        return None
    iesire = cale.with_name(f"{cale.stem}_respinse.csv")
    with iesire.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["linia", "motiv", *COLOANE], extrasaction="ignore")
        w.writeheader()
        w.writerows(rez.respinse)
    return iesire


def importa(conn, cale: Path, sursa: str | None = None, verifica: bool = False, strict: bool = False) -> Rezultat:
    rez = Rezultat(str(cale), comun.sha256(cale))
    randuri = comun.citeste_csv(cale)
    necunoscute = sorted(set().union(*(r.keys() for r in randuri)) - set(COLOANE)) if randuri else []
    if necunoscute:
        rez.avertismente.append(f"coloane ignorate: {', '.join(necunoscute)}")
    valori = pregateste(randuri, sursa, rez)
    if strict and (rez.respinse or rez.avertismente):
        rez.erori += [f"linia {x['linia']}: {x['motiv']}" for x in rez.respinse]
        rez.erori += [a for a in rez.avertismente if a.startswith("linia")]
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
    p.add_argument("--strict", action="store_true", help="orice linie cu probleme oprește tot importul")
    p.add_argument("--detalii", action="store_true", help="arată fiecare corectură, nu doar rezumatul")
    args = p.parse_args(argv)
    if not args.csv.exists():
        print(f"Nu găsesc {args.csv}")
        return 1
    with conecteaza(args.dsn) as conn:
        rez = importa(conn, args.csv, args.sursa, args.verifica, args.strict)
        total, mw = conn.execute("SELECT count(*), coalesce(sum(mw), 0) FROM atr").fetchone()
    corecturi = [a for a in rez.avertismente if a.startswith("linia")]
    for a in rez.avertismente if args.detalii else [a for a in rez.avertismente if a not in corecturi]:
        print(f"AVERTISMENT {a}")
    if corecturi and not args.detalii:
        print(f"{len(corecturi)} corecturi automate (județe, CUI, MW, numere ATR); vedeți-le cu --detalii")
    for e in rez.erori:
        print(f"EROARE      {e}")
    if rez.erori:
        print(f"\n{len(rez.erori)} erori: nu am importat nimic.")
        return 1
    print(f"{args.csv.name}: {rez.linii} linii importate ({rez.inserate} noi, {rez.actualizate} actualizate,"
          f" {rez.neschimbate} neschimbate), {rez.reparate} cu CUI sau MW reparat (reparat=true), {len(rez.respinse)} sărite")
    for x in rez.respinse[:10]:
        print(f"SĂRITĂ      linia {x['linia']}: {x['motiv']}")
    if rez.respinse:
        print(f"Toate liniile sărite, cu motivul: {scrie_respinse(rez, args.csv)}")
    print("Simulare: nimic nu a fost scris în bază." if args.verifica else f"OK: {total} ATR-uri în bază, {mw:.0f} MW.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
