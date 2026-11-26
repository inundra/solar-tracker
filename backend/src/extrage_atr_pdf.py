"""Extrage tabelul din PDF-ul Guvernului cu titularii de ATR într-un CSV pentru `importa_atr.py`.

Folosire:
    pip install pdfplumber
    python backend/src/extrage_atr_pdf.py Lista_titularilor_care_detin_ATR.pdf backend/date_brute/atr_guvern_2026.csv

PDF-ul: https://gov.ro/fisiere/stiri_fisiere/Lista_titularilor_care_detin_ATR.pdf (aprilie–mai 2026).
Nu-l urcați în repo; CSV-ul rezultat e mic și poate intra în backend/date_brute/.

Antetul tabelului se recunoaște după cuvinte cheie (titular, CUI, județ, MW / putere, operator, etapă, PIF),
deci ordinea coloanelor nu contează. Paginile fără antet continuă tabelul de pe pagina anterioară.
Verificați câteva linii din CSV cu PDF-ul înainte de import.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import comun
from importa_atr import COLOANE

# (coloana CSV, expresie căutată în textul antetului fără diacritice). Prima potrivire câștigă.
REGULI_ANTET = [
    ("data_pif", r"\bpif\b|punere in functiune"),
    ("data_atr", r"data.*atr|atr.*data|data emiterii|^data$"),
    ("numar_atr", r"(nr|numar).*(atr|aviz)|^atr$|^nr\.? atr"),
    ("titular", r"titular|denumire|beneficiar|solicitant"),
    ("cui", r"\bcui\b|\bcif\b|cod fiscal|cod unic"),
    ("judet", r"judet"),
    ("mw", r"\bmw\b|putere"),
    ("operator", r"operator|\bosd\b|\bots\b"),
    ("etapa", r"etapa|stadiu|stare"),
    ("localitate", r"localitate|amplasament|\buat\b"),
    ("tehnologie", r"tehnologie|tip (centrala|capacitate)|sursa primara"),
]


def mapeaza_antet(celule: list[str | None]) -> dict[int, str]:
    """{index coloană PDF: coloana CSV}, dacă rândul arată a antet (are cel puțin titular, județ și MW)."""
    harta: dict[int, str] = {}
    for i, c in enumerate(celule):
        text = comun.fara_diacritice(c or "").replace("\n", " ")
        for col, rx in REGULI_ANTET:
            if col not in harta.values() and re.search(rx, text):
                harta[i] = col
                break
    return harta if {"titular", "judet", "mw"} <= set(harta.values()) else {}


def randuri_din_tabele(tabele: list[list[list[str | None]]], harta: dict[int, str] | None = None):
    """Parcurge tabelele (pe pagini, în ordine) și dă liniile de date ca dicționare cu coloanele CSV."""
    for tabel in tabele:
        for celule in tabel:
            noua = mapeaza_antet(celule)
            if noua:
                harta = noua
                continue
            if not harta:
                continue
            rand = {col: re.sub(r"\s+", " ", (celule[i] or "")).strip() for i, col in harta.items() if i < len(celule)}
            if not rand.get("titular") or not rand.get("mw"):
                continue  # rânduri goale, subtotaluri, note de subsol
            if comun.fara_diacritice(rand["titular"]).startswith("total"):
                continue
            yield separa_numar_si_data(rand)


_DATA = re.compile(r"(?<!\d)(\d{1,2}[./-]\d{1,2}[./-](?:\d{4}|\d{2})|\d{4}-\d{2}-\d{2})(?![\d./-]*\d)")


def separa_numar_si_data(rand: dict[str, str]) -> dict[str, str]:
    """„Nr. și dată ATR” vine des într-o singură celulă („1234 / 17.05.2023”): o despărțim."""
    for col in ("numar_atr", "data_atr"):
        v = rand.get(col, "")
        m = _DATA.search(v)
        rest = re.sub(r"^[\s/,;-]*(din)?\s*|[\s/,;-]*(din)?\s*$", "", _DATA.sub("", v)) if m else ""
        if m and rest:
            rand["numar_atr"], rand["data_atr"] = rest, m.group(1)
            break
    return rand


def extrage(pdf: Path) -> list[dict[str, str]]:
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit("Lipsește pdfplumber: pip install pdfplumber")
    with pdfplumber.open(pdf) as doc:
        tabele = [t for pagina in doc.pages for t in pagina.extract_tables()]
    return list(randuri_din_tabele(tabele))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pdf", type=Path)
    p.add_argument("csv", type=Path)
    p.add_argument("--sursa", default="https://gov.ro/fisiere/stiri_fisiere/Lista_titularilor_care_detin_ATR.pdf")
    args = p.parse_args(argv)
    randuri = extrage(args.pdf)
    if not randuri:
        print("N-am găsit niciun tabel cu antet recunoscut (titular, județ, MW). Verificați PDF-ul.")
        return 1
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLOANE)
        w.writeheader()
        for r in randuri:
            w.writerow({c: r.get(c, "") for c in COLOANE} | {"sursa": args.sursa})
    gasite = sorted({c for r in randuri for c in r})
    print(f"OK: {len(randuri)} linii în {args.csv}. Coloane găsite: {', '.join(gasite)}")
    print(f"Următorul pas: python backend/src/importa_atr.py {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
