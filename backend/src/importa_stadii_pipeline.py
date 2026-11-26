"""Importă stadiile prezise de pipeline pentru parcurile din setul de adevăr (tabelele observatii + stadii_pipeline).

Folosire:
    python backend/src/importa_stadii_pipeline.py pipeline/iesiri/stadii_pipeline.csv

Servește validării (v_comparatie_stadii: predicție față de adevăr, lună de lună). Detecțiile noi, din afara
setului de adevăr, intră cu importa_detectii.py.

Coloane: parc_id, luna (AAAA-LL), versiune_model, stadiu, incredere, mwp_estimat, mwp_min, mwp_max,
suprafata_panouri_ha, sursa_imagine, data_imagine, id_imagine, cer_senin.
Obligatorii: parc_id, luna, versiune_model, stadiu. Dacă linia are imaginea (sursa_imagine, data_imagine,
id_imagine), se salvează ca observație și devine dovada stadiului. Cheia e (parc_id, luna, versiune_model):
rularea repetată actualizează, fără duplicate. La orice eroare nu scrie nimic.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import comun
from db import conecteaza

OBLIGATORII = ["parc_id", "luna", "versiune_model", "stadiu"]
STADII = {"teren_gol", "santier", "panouri", "gata", "nesigur"}
SURSE_IMAGINE = {"sentinel-2", "sentinel-1", "google-earth", "planet", "ortofoto", "alta"}

SQL_OBSERVATIE = """
INSERT INTO observatii (parc_id, data_imagine, sursa_imagine, id_imagine, cer_senin, versiune_pipeline)
VALUES (%(parc_id)s, %(data_imagine)s, %(sursa_imagine)s, %(id_imagine)s, %(cer_senin)s, %(versiune_model)s)
ON CONFLICT (parc_id, sursa_imagine, id_imagine, versiune_pipeline)
DO UPDATE SET data_imagine = EXCLUDED.data_imagine, cer_senin = EXCLUDED.cer_senin
RETURNING id
"""

SQL_STADIU = """
INSERT INTO stadii_pipeline (parc_id, luna, versiune_model, stadiu, incredere, mwp_estimat, mwp_min, mwp_max,
                             suprafata_panouri_ha, observatie_id)
VALUES (%(parc_id)s, %(luna)s, %(versiune_model)s, %(stadiu)s, %(incredere)s, %(mwp_estimat)s, %(mwp_min)s,
        %(mwp_max)s, %(suprafata_panouri_ha)s, %(observatie_id)s)
ON CONFLICT (parc_id, luna, versiune_model) DO UPDATE SET
    stadiu = EXCLUDED.stadiu, incredere = EXCLUDED.incredere, mwp_estimat = EXCLUDED.mwp_estimat,
    mwp_min = EXCLUDED.mwp_min, mwp_max = EXCLUDED.mwp_max, suprafata_panouri_ha = EXCLUDED.suprafata_panouri_ha,
    observatie_id = EXCLUDED.observatie_id, rulat_la = now()
RETURNING (xmax = 0) AS inserat
"""


def pregateste(randuri: list[dict], parcuri: set[str], erori: list[str]) -> list[dict]:
    curate = []
    for nr, r in enumerate(randuri, start=2):
        try:
            lipsa = [c for c in OBLIGATORII if not r.get(c)]
            if lipsa:
                raise ValueError(f"lipsesc {', '.join(lipsa)}")
            if r["parc_id"] not in parcuri:
                raise ValueError(f"parcul {r['parc_id']} nu e în bază (importați întâi parcuri.csv)")
            if not re.fullmatch(r"\d{4}-\d{2}", r["luna"]):
                raise ValueError(f"luna „{r['luna']}” nu e AAAA-LL")
            if r["stadiu"] not in STADII:
                raise ValueError(f"stadiul „{r['stadiu']}” nu e permis")
            imagine = [r.get(c) for c in ("sursa_imagine", "data_imagine", "id_imagine")]
            if any(imagine) and not all(imagine):
                raise ValueError("imaginea are nevoie de toate trei: sursa_imagine, data_imagine, id_imagine")
            if r.get("sursa_imagine") and r["sursa_imagine"] not in SURSE_IMAGINE:
                raise ValueError(f"sursa_imagine „{r['sursa_imagine']}” nu e permisă")
            v = {c: r.get(c) for c in ("parc_id", "versiune_model", "stadiu", "sursa_imagine", "id_imagine")}
            v["luna"] = comun.data(r["luna"])
            v["data_imagine"] = comun.data(r.get("data_imagine"))
            if v["data_imagine"] and v["data_imagine"].replace(day=1) != v["luna"]:
                raise ValueError(f"data_imagine {v['data_imagine']} nu e în luna {r['luna']}")
            for c in ("incredere", "cer_senin", "mwp_estimat", "mwp_min", "mwp_max", "suprafata_panouri_ha"):
                v[c] = comun.numar(r.get(c))
            for c in ("incredere", "cer_senin"):
                if v[c] is not None and not 0 <= v[c] <= 1:
                    raise ValueError(f"{c}={v[c]} trebuie să fie între 0 și 1")
            curate.append(v)
        except ValueError as e:
            erori.append(f"linia {nr}: {e}")
    return curate


def importa(conn, cale: Path) -> tuple[list[str], int, int]:
    """Întoarce (erori, inserate, actualizate)."""
    erori: list[str] = []
    parcuri = {r[0] for r in conn.execute("SELECT parc_id FROM parcuri")}
    valori = pregateste(comun.citeste_csv(cale), parcuri, erori)
    if erori:
        return erori, 0, 0
    inserate = actualizate = 0
    with conn.transaction():
        for v in valori:
            v["observatie_id"] = conn.execute(SQL_OBSERVATIE, v).fetchone()[0] if v["id_imagine"] else None
            if conn.execute(SQL_STADIU, v).fetchone()[0]:
                inserate += 1
            else:
                actualizate += 1
        comun.noteaza_import(conn, str(cale), comun.sha256(cale), len(valori), inserate, actualizate, 0)
    return erori, inserate, actualizate


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", type=Path)
    p.add_argument("--dsn", help="adresa bazei (altfel DATABASE_URL)")
    args = p.parse_args(argv)
    with conecteaza(args.dsn) as conn:
        erori, ins, act = importa(conn, args.csv)
    for e in erori:
        print(f"EROARE      {e}")
    if erori:
        print(f"\n{len(erori)} erori: nu am importat nimic.")
        return 1
    print(f"OK: {ins} stadii noi, {act} actualizate.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
