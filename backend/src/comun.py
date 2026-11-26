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
_JUDETE_DUPA_NUME |= {"bucuresti": "B", "municipiul bucuresti": "B", "mun. bucuresti": "B", "mun bucuresti": "B"}
# Reședințele de județ, pentru celulele în care apare orașul în loc de județ („Timisoara”).
_RESEDINTE = {
    "alba iulia": "AB", "arad": "AR", "pitesti": "AG", "bacau": "BC", "oradea": "BH", "bistrita": "BN",
    "botosani": "BT", "brasov": "BV", "braila": "BR", "buzau": "BZ", "resita": "CS", "calarasi": "CL",
    "cluj napoca": "CJ", "constanta": "CT", "sfantu gheorghe": "CV", "targoviste": "DB", "craiova": "DJ",
    "galati": "GL", "giurgiu": "GR", "targu jiu": "GJ", "miercurea ciuc": "HR", "deva": "HD", "slobozia": "IL",
    "iasi": "IS", "buftea": "IF", "baia mare": "MM", "drobeta turnu severin": "MH", "targu mures": "MS",
    "piatra neamt": "NT", "slatina": "OT", "ploiesti": "PH", "satu mare": "SM", "zalau": "SJ", "sibiu": "SB",
    "suceava": "SV", "alexandria": "TR", "timisoara": "TM", "tulcea": "TL", "vaslui": "VS",
    "ramnicu valcea": "VL", "focsani": "VN",
}


def _curata_judet(v: str) -> str:
    n = fara_diacritice(v)
    n = re.sub(r"[\u2010-\u2015\-_/.]", " ", n)          # cratime, liniuțe de tot felul
    n = re.sub(r"^(judetul|judet|jud)\s+", "", n.strip())
    return re.sub(r"\s+", " ", n).strip()


def _fara_dublare(text: str) -> str:
    """„BBUUCCUURREESSTTII” → „BUCURESTI” (litere dublate de PDF-urile cu text îngroșat)."""
    t = text.replace(" ", "")
    if len(t) >= 4 and len(t) % 2 == 0 and all(t[i] == t[i + 1] for i in range(0, len(t), 2)):
        return t[::2]
    return text


def cod_judet(valoare: str | None, aproximativ: bool = False) -> str | None:
    """Codul auto al județului, din cod („DJ”) sau din nume („Dolj”, „DOLJ”, „jud. Dolj”, „Dambovita”).

    Cu aproximativ=True acceptă și greșeli de tastare („Dambovta”, „BISTRITA NASAU”), litere dublate
    și reședința județului în loc de județ („Timisoara”)."""
    if not valoare:
        return None
    v = valoare.strip()
    if v.upper() in JUDETE:
        return v.upper()
    n = _curata_judet(v)
    if n in _JUDETE_DUPA_NUME:
        return _JUDETE_DUPA_NUME[n]
    if not aproximativ:
        return None
    n = _curata_judet(_fara_dublare(v))
    if n.upper() in JUDETE:
        return n.upper()
    if n in _JUDETE_DUPA_NUME:
        return _JUDETE_DUPA_NUME[n]
    if n in _RESEDINTE:
        return _RESEDINTE[n]
    import difflib
    nume = list(_JUDETE_DUPA_NUME) + list(_RESEDINTE)
    potrivire = difflib.get_close_matches(n, nume, n=1, cutoff=0.8)
    if potrivire:
        return _JUDETE_DUPA_NUME.get(potrivire[0]) or _RESEDINTE[potrivire[0]]
    return None


def judete_din_text(valoare: str | None) -> list[str]:
    """Toate județele dintr-o celulă: „Arad si Timis” → [AR, TM]; „Dâmbovița, Ilfov” → [DB, IF];
    „Gorj Oltenia SA)” (text vărsat din coloana vecină) → [GJ]. Ordinea din text se păstrează."""
    if not valoare:
        return []
    unul = cod_judet(valoare, aproximativ=True)
    if unul:
        return [unul]
    gasite = []
    for parte in re.split(r"\s*(?:,|;|\+|&|/|\bsi\b|\bși\b)\s*", valoare, flags=re.I):
        cod = cod_judet(parte, aproximativ=True) if parte.strip() else None
        if cod and cod not in gasite:
            gasite.append(cod)
    if gasite:
        return gasite
    # Ultima variantă: numele unui județ apare ca cuvinte întregi în text.
    n = " " + _curata_judet(valoare) + " "
    candidati = [(n.find(f" {nume} "), c) for nume, c in _JUDETE_DUPA_NUME.items() if f" {nume} " in n]
    return [c for _, c in sorted(candidati)][:1]


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
    """Data din „2023-05-17”, „17.05.2023”, „17/05/2023”, „17-05-2023”, „10/21/2025” (lună/zi, când ziua > 12)
    sau „05.2023” (prima zi a lunii). O zi care nu există („31.06.2026”) devine ultima zi a lunii."""
    if not valoare or not str(valoare).strip():
        return None
    v = str(valoare).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%y", "%m/%d/%Y", "%m.%Y", "%m/%Y", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", v)
    if m:
        zi, luna, an = (int(x) for x in m.groups())
        if 1 <= luna <= 12 and 28 < zi <= 31:
            import calendar
            return date(an, luna, calendar.monthrange(an, luna)[1])
    raise ValueError(f"nu înțeleg data „{v}”")


_DATA_IN_TEXT = re.compile(r"(?<!\d)(\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{4}-\d{2}-\d{2})(?!\d)")


def pif(valoare: str | None) -> tuple[str | None, date | None, int | None]:
    """Interpretează celula PIF din lista ATR. Întoarce (stare, data, an).

    „PIF estimat la 31.12.2027” → (estimat, 2027-12-31, 2027); „Pif estimat 2033” → (estimat, None, 2033);
    „PIF/11.04.2012”, „PIF 2014”, „Finalizat cu PIF” → (realizat, ...); „Anulat” → (anulat, None, None);
    o dată simplă („12.2026”) → (estimat, ...). Textul original se păstrează separat."""
    if not valoare or not str(valoare).strip():
        return None, None, None
    text = str(valoare).strip()
    n = fara_diacritice(text).replace("(cid:415)", "ti")
    if "anulat" in n:
        stare = "anulat"
    elif "retehnologiz" in n:
        stare = "retehnologizat"
    elif "estimat" in n or "estimata" in n:
        stare = "estimat"
    elif "finalizat" in n or re.match(r"^pif\b", n):
        stare = "realizat"
    else:
        stare = "estimat"
    zi = None
    m = _DATA_IN_TEXT.search(text)
    if m:
        try:
            zi = data(m.group(1))
        except ValueError:
            zi = None
    elif re.fullmatch(r"\d{1,2}[./]\d{4}|\d{4}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", text):
        zi = data(text)
    an = zi.year if zi else None
    if an is None:
        ani = re.findall(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", text)
        an = int(ani[0]) if ani else None
    if stare == "estimat" and zi is None and an is None and not re.search(r"\d", n):
        stare = "necunoscut"
    return stare, zi, an


def cui(valoare: str | None) -> str | None:
    """„RO 12345678” → „12345678”. Gol → None."""
    if not valoare:
        return None
    v = re.sub(r"(?i)^ro", "", re.sub(r"\s", "", str(valoare)))
    return v or None


def cui_tolerant(valoare: str | None) -> tuple[str | None, bool]:
    """CUI-ul dintr-o celulă murdară: „L. 45427207”, „SRL21566895”, „ROMANIA SRL 22160860” → cifrele.
    Întoarce (cui, reparat): reparat=True când am scos și altceva decât prefixul RO și spațiile."""
    curat = cui(valoare)
    if curat is None or re.fullmatch(r"[0-9]{2,10}", curat):
        return curat, False
    tokeni = re.findall(r"(?<![0-9])[0-9]{2,10}(?![0-9])", str(valoare).replace(" ", " "))
    if len(tokeni) == 1:
        return tokeni[0], True
    cifre = re.sub(r"[^0-9]", "", str(valoare))
    if 2 <= len(cifre) <= 10:
        return cifre, True
    return None, True


def mw_tolerant(valoare: str | None) -> tuple[float | None, bool]:
    """MW dintr-o celulă: „45,5” sau „HSA 0.69” (text vărsat din coloana vecină) → (45.5, False) / (0.69, True).
    Dacă cifrele sunt amestecate cu litere („3S2R1L7).16”), nu ghicim: (None, True)."""
    if valoare is None or not str(valoare).strip():
        return None, False
    try:
        return numar(valoare), False
    except ValueError:
        pass
    tokeni = re.findall(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w.,])", str(valoare))
    if len(tokeni) == 1:
        return numar(tokeni[0]), True
    m = re.fullmatch(r"[^\d]*?(\d+(?:[.,]\d+)?)\s*(?:mw)?", str(valoare).strip(), flags=re.I)
    if m:
        return numar(m.group(1)), True
    return None, True


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
