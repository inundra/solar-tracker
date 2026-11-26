"""Leagă detecțiile de ATR-uri: propune candidați cu scor, apoi un om îi confirmă sau îi respinge.

Folosire:
    python backend/src/leaga_atr.py propune                   # pentru toate detecțiile nelegate
    python backend/src/leaga_atr.py propune --judet DJ
    python backend/src/leaga_atr.py lista --judet DJ          # candidații, cu scor și motive
    python backend/src/leaga_atr.py confirma DJ-2026-0007 412 --de AlexandruAchilleF --note "APM Dolj, anunț 2025"
    python backend/src/leaga_atr.py respinge DJ-2026-0007 398 --de AlexandruAchilleF

Cum se calculează scorul (0–1). Lista ATR are doar județul, deci candidații sunt ATR-urile din același județ,
cu tehnologie compatibilă, notați după:
- CUI: dacă detecția e un parc din setul de adevăr cu același CUI ca ATR-ul, scorul e 1;
- MW (55%): MWp detectați / raportul DC/AC, comparat cu MW din ATR (1 la potrivire, 0 la un factor de 3);
- loc (35%): localitatea detecției apare în numele titularului sau în localitatea ATR-ului;
- timp (10%): construcția n-a început cu peste un an înainte de data ATR-ului.
Se păstrează cel mult 5 candidați cu scor ≥ 0,35. Legăturile confirmate sau respinse nu se ating la o nouă propunere.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass

import psycopg

import comun
from db import conecteaza

PONDERI = {"mw": 0.55, "loc": 0.35, "timp": 0.10}
PRAG = 0.35
MAX_CANDIDATI = 5
COMPATIBIL = {
    "fotovoltaic": {"fotovoltaic", "hibrid", "necunoscuta"},
    "stocare": {"stocare", "hibrid", "necunoscuta"},
    "necunoscut": {"fotovoltaic", "stocare", "hibrid", "eolian", "alta", "necunoscuta"},
}


@dataclass
class Candidat:
    atr_id: int
    scor: float
    motive: dict


def _cuvinte(text: str | None) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", comun.fara_diacritice(text or "")) if len(w) >= 3}


def scor_mw(mwp: float | None, mw_atr: float, dc_ac: float) -> float | None:
    if not mwp or not mw_atr:
        return None
    r = (mwp / dc_ac) / mw_atr
    return max(0.0, 1 - abs(math.log(r)) / math.log(3))


def scor_loc(uat: str | None, titular: str, localitate: str | None) -> float:
    """1 dacă toate cuvintele din UAT apar în titular sau în localitatea ATR-ului („Corbii Mari” → „Corbii Mari Solar”)."""
    loc = _cuvinte(uat)
    if not loc:
        return 0.0
    return 1.0 if loc <= _cuvinte(titular) or loc <= _cuvinte(localitate) else 0.0


def scor_timp(data_defrisare, data_atr) -> float:
    if not data_defrisare or not data_atr:
        return 1.0
    return 0.0 if (data_atr - data_defrisare).days > 365 else 1.0


def candidati(d: dict, atr_uri: list[dict], dc_ac: float) -> list[Candidat]:
    rez = []
    for a in atr_uri:
        if a["tehnologie"] not in COMPATIBIL[d["tip"]]:
            continue
        if d["cui_parc"] and a["cui"] and d["cui_parc"] == a["cui"]:
            rez.append(Candidat(a["id"], 1.0, {"cui": a["cui"]}))
            continue
        s_mw = scor_mw(d["mwp"], a["mw"], dc_ac)
        s_loc = scor_loc(d["uat"], a["titular"], a["localitate"])
        s_timp = scor_timp(d["data_defrisare"], a["data_atr"])
        scor = PONDERI["mw"] * (s_mw or 0) + PONDERI["loc"] * s_loc + PONDERI["timp"] * s_timp
        if scor >= PRAG:
            rez.append(Candidat(a["id"], round(scor, 3), {
                "mw": None if s_mw is None else round(s_mw, 2), "loc": s_loc, "timp": s_timp,
                "mwp_detectat": d["mwp"], "mw_atr": a["mw"],
            }))
    rez.sort(key=lambda c: c.scor, reverse=True)
    return rez[:MAX_CANDIDATI]


def _dict(cur) -> list[dict]:
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def propune(conn, judet: str | None = None) -> dict[str, int]:
    """Recalculează candidații pentru detecțiile fără ATR confirmat. Întoarce {detectie_id: nr. candidați}."""
    dc_ac = float(conn.execute("SELECT parametru('dc_ac')").fetchone()[0])
    detectii = _dict(conn.execute(
        "SELECT d.detectie_id, d.judet, d.uat, d.tip, d.mwp::float8 AS mwp, d.data_defrisare, p.cui AS cui_parc"
        " FROM v_detectii d LEFT JOIN parcuri p USING (parc_id)"
        " WHERE d.atr_id IS NULL AND d.duplicat_al IS NULL AND (%(j)s::text IS NULL OR d.judet = %(j)s)",
        {"j": judet}))
    atr_pe_judet: dict[str, list[dict]] = {}
    for a in _dict(conn.execute(
            "SELECT id, judet, titular, cui, mw::float8 AS mw, tehnologie, localitate, data_atr FROM atr"
            " WHERE %(j)s::text IS NULL OR judet = %(j)s", {"j": judet})):
        atr_pe_judet.setdefault(a["judet"], []).append(a)

    rezultat = {}
    with conn.transaction():
        for d in detectii:
            respinse = {r[0] for r in conn.execute(
                "SELECT atr_id FROM legaturi_atr WHERE detectie_id = %s AND stare = 'respinsa'", (d["detectie_id"],))}
            conn.execute("DELETE FROM legaturi_atr WHERE detectie_id = %s AND stare = 'propusa'", (d["detectie_id"],))
            lista = [c for c in candidati(d, atr_pe_judet.get(d["judet"], []), dc_ac) if c.atr_id not in respinse]
            for c in lista:
                conn.execute(
                    "INSERT INTO legaturi_atr (detectie_id, atr_id, scor, motive) VALUES (%s, %s, %s, %s)",
                    (d["detectie_id"], c.atr_id, c.scor, json.dumps(c.motive)))
            rezultat[d["detectie_id"]] = len(lista)
    return rezultat


def decide(conn, detectie_id: str, atr_id: int, stare: str, de: str, note: str | None = None) -> None:
    with conn.transaction():
        conn.execute(
            "INSERT INTO legaturi_atr (detectie_id, atr_id, scor, motive, stare, decis_de, decis_la, note)"
            " VALUES (%(d)s, %(a)s, 0, '{\"manual\": true}', %(s)s, %(de)s, now(), %(n)s)"
            " ON CONFLICT (detectie_id, atr_id) DO UPDATE SET stare = EXCLUDED.stare, decis_de = EXCLUDED.decis_de,"
            " decis_la = now(), note = coalesce(EXCLUDED.note, legaturi_atr.note)",
            {"d": detectie_id, "a": atr_id, "s": stare, "de": de, "n": note})
        if stare == "confirmata":
            # Ceilalți candidați nu mai sunt necesari; localitatea ATR-ului se completează din detecție.
            conn.execute("DELETE FROM legaturi_atr WHERE detectie_id = %s AND stare = 'propusa'", (detectie_id,))
            conn.execute(
                "UPDATE atr SET localitate = coalesce(atr.localitate, d.uat), actualizat_la = now()"
                " FROM detectii d WHERE atr.id = %s AND d.detectie_id = %s AND atr.localitate IS NULL AND d.uat IS NOT NULL",
                (atr_id, detectie_id))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dsn", help="adresa bazei (altfel DATABASE_URL)")
    sub = p.add_subparsers(dest="comanda", required=True)
    pr = sub.add_parser("propune")
    pr.add_argument("--judet")
    ls = sub.add_parser("lista")
    ls.add_argument("--judet")
    for nume in ("confirma", "respinge"):
        c = sub.add_parser(nume)
        c.add_argument("detectie_id")
        c.add_argument("atr_id", type=int)
        c.add_argument("--de", required=True, help="login GitHub al celui care decide")
        c.add_argument("--note")
    args = p.parse_args(argv)
    judet = comun.cod_judet(getattr(args, "judet", None)) if getattr(args, "judet", None) else None

    with conecteaza(args.dsn) as conn:
        if args.comanda == "propune":
            rez = propune(conn, judet)
            cu = sum(1 for n in rez.values() if n)
            print(f"OK: {len(rez)} detecții nelegate, {cu} cu cel puțin un candidat, {sum(rez.values())} candidați în total.")
        elif args.comanda == "lista":
            for r in conn.execute(
                    "SELECT l.detectie_id, d.uat, round(d.mwp, 1), a.id, a.titular, a.mw, l.scor, l.motive"
                    " FROM legaturi_atr l JOIN v_detectii d USING (detectie_id) JOIN atr a ON a.id = l.atr_id"
                    " WHERE l.stare = 'propusa' AND (%(j)s::text IS NULL OR d.judet = %(j)s)"
                    " ORDER BY l.detectie_id, l.scor DESC", {"j": judet}):
                print(f"{r[0]:<18} {r[1] or '-':<16} {r[2] or '-':>7} MWp  →  ATR {r[3]:<6} {r[4][:40]:<40} {r[5]:>8} MW"
                      f"  scor {r[6]}  {json.dumps(r[7], ensure_ascii=False)}")
        else:
            stare = "confirmata" if args.comanda == "confirma" else "respinsa"
            try:
                decide(conn, args.detectie_id, args.atr_id, stare, args.de, args.note)
            except psycopg.errors.UniqueViolation:
                print(f"{args.detectie_id} are deja un ATR confirmat. Respingeți-l întâi dacă era greșit.")
                return 1
            except psycopg.errors.ForeignKeyViolation:
                print(f"Nu există detecția {args.detectie_id} sau ATR-ul {args.atr_id}.")
                return 1
            print(f"OK: {args.detectie_id} ↔ ATR {args.atr_id}: {stare}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
