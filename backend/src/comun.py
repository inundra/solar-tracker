"""Funcții mici comune importurilor: texte fără diacritice, județe, numere și date scrise în mai multe feluri."""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

JUDETE = {
    "AB": "Alba", "AR": "Arad", "AG": "Argeș", "BC": "Bacău", "BH": "Bihor", "BN": "Bistrița-Năsăud",
    "BT": "Botoșani", "BV": "Brașov", "BR": "Brăila", "B": "București", "BZ": "Buzău", "CS": "Caraș-Severin",
    "CL": "Călărași", "CJ": "Cluj", "CT": "Constanța", "CV": "Covasna", "DB": "Dâmbovița", "DJ": "Dolj",
    "GL": "Galați", "GR": "Giurgiu", "GJ": "Gorj", "HR": "Harghita", "HD": "Hunedoara", "IL": "Ialomița",
    "IS": "Iași", "IF": "Ilfov", "MM": "Maramureș", "MH": "Mehedinți", "MS": "Mureș", "NT": "Neamț",
    "OT": "Olt", "PH": "Prahova", "SM": "Satu Mare", "SJ": "Sălaj", "SB": "Sibiu", "SV": "Suceava",
    "TR": "Teleorman", "TM": "Timiș", "TL": "Tulcea", "VS": "Vaslui", "VL": "Vâlcea", "VN": "Vrancea",
}


def fara_diacritice(text: str) -> str:
    """„Ișalnița” → „isalnita” (litere mici, fără diacritice, spații simple)."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


_JUDETE_DUPA_NUME = {fara_diacritice(n).replace("-", " "): c for c, n in JUDETE.items()}
_JUDETE_DUPA_NUME |= {"bucuresti": "B", "municipiul bucuresti": "B", "mun. bucuresti": "B"}


def cod_judet(valoare: str | None) -> str | None:
    """Codul auto al județului, din cod („DJ”) sau din nume („Dolj”, „DOLJ”, „jud. Dolj”, „Dambovita”)."""
    if not valoare:
        return None
    v = valoare.strip()
    if v.upper() in JUDETE:
        return v.upper()
    n = fara_diacritice(v).replace("-", " ")
    n = re.sub(r"^(judetul|judet|jud\.?)\s+", "", n)
    return _JUDETE_DUPA_NUME.get(n)


def numar(valoare: str | None) -> float | None:
    """„12,5” / „12.5” / „1.234,5” / „1 234.5 MW” → float. Gol → None."""
    if valoare is None:
        return None
    v = re.sub(r"(?i)\s*(mwp|mwac|mw)\s*$", "", str(valoare).strip()).replace(" ", "").replace(" ", "")
    if not v:
        return None
    if "," in v and "." in v:
        v = v.replace(".", "").replace(",", ".") if v.rfind(",") > v.rfind(".") else v.replace(",", "")
    elif "," in v:
        v = v.replace(",", ".")
    return float(v)


def data(valoare: str | None) -> date | None:
    """Data din „2023-05-17”, „17.05.2023”, „17/05/2023”, „17-05-2023” sau „05.2023” (prima zi a lunii)."""
    if not valoare or not str(valoare).strip():
        return None
    v = str(valoare).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%y", "%m.%Y", "%m/%Y", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"nu înțeleg data „{v}”")


def cui(valoare: str | None) -> str | None:
    """„RO 12345678” → „12345678”. Gol → None."""
    if not valoare:
        return None
    v = re.sub(r"(?i)^ro", "", re.sub(r"\s", "", str(valoare)))
    return v or None


def citeste_csv(cale: Path) -> list[dict[str, str | None]]:
    """Liniile unui CSV UTF-8 (cu sau fără BOM), cu celulele goale transformate în None."""
    text = cale.read_text(encoding="utf-8-sig")
    randuri = []
    for rand in csv.DictReader(text.splitlines()):
        curat = {k.strip(): (v or "").strip() or None for k, v in rand.items() if k is not None}
        if any(curat.values()):
            randuri.append(curat)
    return randuri


def sha256(cale: Path) -> str:
    return hashlib.sha256(cale.read_bytes()).hexdigest()


def noteaza_import(conn, fisier: str, hash_: str, linii: int, inserate: int, actualizate: int,
                   neschimbate: int, sterse: int = 0) -> None:
    conn.execute(
        "INSERT INTO importuri (fisier, sha256, linii, inserate, actualizate, neschimbate, sterse)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (fisier, hash_, linii, inserate, actualizate, neschimbate, sterse),
    )
