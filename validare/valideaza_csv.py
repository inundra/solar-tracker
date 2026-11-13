"""Verifică parcuri.csv și stadii_lunare.csv după validare/schema_csv.md.

Folosire:
    python validare/valideaza_csv.py validare/parcuri.csv validare/stadii_lunare.csv
    python validare/valideaza_csv.py validare/parcuri.csv          # doar lista de parcuri

Fără dependențe: doar biblioteca standard Python 3.9+.
Iese cu codul 1 dacă există erori; avertismentele nu opresc verificarea.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

STADII = ["teren_gol", "santier", "panouri", "gata", "nesigur"]
ORDINE_STADII = {"teren_gol": 0, "santier": 1, "panouri": 2, "gata": 3}
SURSE_IMAGINE = {"sentinel-2", "sentinel-1", "google-earth", "planet", "ortofoto", "alta"}
ROLURI = {"track", "check", "test", "lista"}
JUDETE = {
    "AB", "AR", "AG", "BC", "BH", "BN", "BT", "BV", "BR", "B", "BZ", "CS", "CL", "CJ",
    "CT", "CV", "DB", "DJ", "GL", "GR", "GJ", "HR", "HD", "IL", "IS", "IF", "MM", "MH",
    "MS", "NT", "OT", "PH", "SM", "SJ", "SB", "SV", "TR", "TM", "TL", "VS", "VL", "VN",
}

COLOANE_PARCURI = [
    "parc_id", "nume", "judet", "uat", "lat", "lon", "are_poligon", "mwp", "mwac",
    "sursa_mw", "detinator", "cui", "atr_numar", "atr_data", "atr_mw", "rol",
    "stadiu_curent", "data_verificare", "sursa", "verificat_de", "note",
]
OBLIGATORII_PARCURI = [
    "parc_id", "nume", "judet", "lat", "lon", "are_poligon", "rol",
    "stadiu_curent", "data_verificare", "sursa", "verificat_de",
]
COLOANE_STADII = [
    "parc_id", "luna", "stadiu", "sursa_imagine", "data_imagine", "id_imagine",
    "verificat_de", "note",
]
OBLIGATORII_STADII = ["parc_id", "luna", "stadiu", "verificat_de"]

RE_PARC_ID = re.compile(r"^(?P<judet>[A-Z]{1,2})-\d{3}$")
RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_LUNA = re.compile(r"^\d{4}-\d{2}$")
RE_CUI = re.compile(r"^\d{2,10}$")


class Raport:
    def __init__(self) -> None:
        self.erori: list[str] = []
        self.avertismente: list[str] = []

    def eroare(self, fisier: str, linie: int, mesaj: str) -> None:
        self.erori.append(f"{fisier}:{linie}: {mesaj}")

    def avertisment(self, fisier: str, linie: int, mesaj: str) -> None:
        self.avertismente.append(f"{fisier}:{linie}: {mesaj}")


def citeste(cale: Path, raport: Raport, coloane: list[str], obligatorii: list[str]):
    text = cale.read_text(encoding="utf-8-sig")
    antet = text.splitlines()[0] if text else ""
    if ";" in antet and "," not in antet:
        raport.eroare(cale.name, 1, "separatorul e ';'. Salvați ca „CSV UTF-8 (delimitat prin virgulă)”.")
        return []
    cititor = csv.DictReader(text.splitlines())
    gasite = cititor.fieldnames or []
    for col in obligatorii:
        if col not in gasite:
            raport.eroare(cale.name, 1, f"lipsește coloana obligatorie „{col}”")
    for col in gasite:
        if col not in coloane:
            raport.avertisment(cale.name, 1, f"coloană necunoscută „{col}” (va fi ignorată la import)")
    if any(col not in gasite for col in obligatorii):
        return []
    randuri = []
    for nr, rand in enumerate(cititor, start=2):
        if None in rand:
            raport.eroare(cale.name, nr, "linia are mai multe celule decât antetul (o virgulă în plus?)")
        curat = {k: (v or "").strip() for k, v in rand.items() if k is not None}
        if not any(curat.values()):
            continue
        randuri.append((nr, curat))
    return randuri


def e_data(valoare: str) -> bool:
    if not RE_DATA.match(valoare):
        return False
    try:
        date.fromisoformat(valoare)
    except ValueError:
        return False
    return True


def e_zecimal(valoare: str) -> bool:
    try:
        return float(valoare) >= 0
    except ValueError:
        return False


def verifica_parcuri(cale: Path, raport: Raport) -> set[str]:
    f = cale.name
    ids: set[str] = set()
    for nr, r in citeste(cale, raport, COLOANE_PARCURI, OBLIGATORII_PARCURI):
        for col in OBLIGATORII_PARCURI:
            if not r.get(col):
                raport.eroare(f, nr, f"„{col}” e obligatoriu")

        pid = r["parc_id"]
        m = RE_PARC_ID.match(pid)
        if pid and not m:
            raport.eroare(f, nr, f"parc_id „{pid}” nu are forma JJ-NNN (ex. DJ-001)")
        if pid in ids:
            raport.eroare(f, nr, f"parc_id „{pid}” apare de două ori")
        ids.add(pid)

        judet = r["judet"]
        if judet and judet not in JUDETE:
            raport.eroare(f, nr, f"județul „{judet}” nu e un cod auto valid (ex. DJ, GJ, B)")
        if m and judet and m.group("judet") != judet:
            raport.avertisment(f, nr, f"parc_id „{pid}” nu începe cu județul „{judet}”")

        for col, mn, mx in (("lat", 43.6, 48.3), ("lon", 20.2, 29.8)):
            v = r[col]
            if not v:
                continue
            if "," in v:
                raport.eroare(f, nr, f"{col} „{v}” folosește virgulă zecimală; folosiți punct")
                continue
            try:
                x = float(v)
            except ValueError:
                raport.eroare(f, nr, f"{col} „{v}” nu e număr")
                continue
            if not mn <= x <= mx:
                raport.eroare(f, nr, f"{col} {x} e în afara României ({mn}–{mx}); ați inversat lat/lon?")

        if r["are_poligon"] and r["are_poligon"] not in ("da", "nu"):
            raport.eroare(f, nr, "are_poligon trebuie să fie „da” sau „nu”")
        if r["are_poligon"] == "da":
            geo = cale.parent / "proiecte_cartate" / f"{pid}.geojson"
            if not geo.exists():
                raport.avertisment(f, nr, f"are_poligon=da, dar nu găsesc {geo}")

        for col in ("mwp", "mwac", "atr_mw"):
            if r.get(col) and not e_zecimal(r[col]):
                raport.eroare(f, nr, f"{col} „{r[col]}” nu e număr pozitiv cu punct zecimal")
        if (r.get("mwp") or r.get("mwac")) and not r.get("sursa_mw"):
            raport.eroare(f, nr, "mwp/mwac completat fără sursa_mw")

        if r.get("cui") and not RE_CUI.match(r["cui"]):
            raport.eroare(f, nr, f"cui „{r['cui']}” trebuie să fie doar cifre, fără RO")

        for col in ("atr_data", "data_verificare"):
            if r.get(col) and not e_data(r[col]):
                raport.eroare(f, nr, f"{col} „{r[col]}” nu e o dată AAAA-LL-ZZ")
        if r["data_verificare"] and e_data(r["data_verificare"]) and date.fromisoformat(r["data_verificare"]) > date.today():
            raport.eroare(f, nr, "data_verificare e în viitor")

        if r["rol"] and r["rol"] not in ROLURI:
            raport.eroare(f, nr, f"rol „{r['rol']}” nu e permis ({', '.join(sorted(ROLURI))})")
        if r["stadiu_curent"] and r["stadiu_curent"] not in STADII:
            raport.eroare(f, nr, f"stadiu_curent „{r['stadiu_curent']}” nu e permis ({', '.join(STADII)})")
    return ids


def verifica_stadii(cale: Path, raport: Raport, ids_parcuri: set[str]) -> None:
    f = cale.name
    vazute: set[tuple[str, str]] = set()
    pe_parc: dict[str, list[tuple[str, str, int]]] = {}
    luna_curenta = date.today().strftime("%Y-%m")
    for nr, r in citeste(cale, raport, COLOANE_STADII, OBLIGATORII_STADII):
        for col in OBLIGATORII_STADII:
            if not r.get(col):
                raport.eroare(f, nr, f"„{col}” e obligatoriu")

        pid, luna, stadiu = r["parc_id"], r["luna"], r["stadiu"]
        if pid and pid not in ids_parcuri:
            raport.eroare(f, nr, f"parc_id „{pid}” nu există în lista de parcuri")
        if luna and not RE_LUNA.match(luna):
            raport.eroare(f, nr, f"luna „{luna}” nu are forma AAAA-LL")
        elif luna and not ("2024-01" <= luna <= luna_curenta):
            raport.eroare(f, nr, f"luna {luna} e în afara intervalului 2024-01 – {luna_curenta}")
        if (pid, luna) in vazute:
            raport.eroare(f, nr, f"({pid}, {luna}) apare de două ori")
        vazute.add((pid, luna))

        if stadiu and stadiu not in STADII:
            raport.eroare(f, nr, f"stadiu „{stadiu}” nu e permis ({', '.join(STADII)})")

        sursa, data_img = r.get("sursa_imagine", ""), r.get("data_imagine", "")
        if stadiu and stadiu != "nesigur":
            if not sursa:
                raport.eroare(f, nr, "sursa_imagine e obligatorie când stadiul nu e „nesigur”")
            if not data_img:
                raport.eroare(f, nr, "data_imagine e obligatorie când stadiul nu e „nesigur”")
        if sursa and sursa not in SURSE_IMAGINE:
            raport.eroare(f, nr, f"sursa_imagine „{sursa}” nu e permisă ({', '.join(sorted(SURSE_IMAGINE))})")
        if data_img:
            if not e_data(data_img):
                raport.eroare(f, nr, f"data_imagine „{data_img}” nu e o dată AAAA-LL-ZZ")
            elif luna and not data_img.startswith(luna):
                raport.eroare(f, nr, f"data_imagine {data_img} nu cade în luna {luna}")

        if pid and RE_LUNA.match(luna or "") and stadiu in STADII:
            pe_parc.setdefault(pid, []).append((luna, stadiu, nr))

    for pid, linii in pe_parc.items():
        linii.sort()
        anterior = None
        for luna, stadiu, nr in linii:
            if stadiu == "nesigur":
                anterior = None
                continue
            if anterior and ORDINE_STADII[stadiu] < ORDINE_STADII[anterior]:
                raport.avertisment(f, nr, f"{pid}: stadiul scade de la „{anterior}” la „{stadiu}” în {luna}; explicați în note")
            anterior = stadiu


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print(__doc__)
        return 2
    raport = Raport()
    ids = verifica_parcuri(Path(argv[0]), raport)
    if len(argv) == 2:
        verifica_stadii(Path(argv[1]), raport, ids)

    for a in raport.avertismente:
        print(f"AVERTISMENT {a}")
    for e in raport.erori:
        print(f"EROARE      {e}")
    if raport.erori:
        print(f"\n{len(raport.erori)} erori, {len(raport.avertismente)} avertismente.")
        return 1
    print(f"OK: {len(ids)} parcuri verificate, {len(raport.avertismente)} avertismente.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
