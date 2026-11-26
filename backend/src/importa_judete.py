"""Încarcă conturul județelor (opțional) dintr-un GeoJSON, pentru harta pe județe și pentru detecțiile fără județ.

Folosire:
    python backend/src/importa_judete.py judete_romania.geojson

Orice GeoJSON cu un Feature (Polygon / MultiPolygon, WGS84) pe județ merge, de exemplu geoBoundaries ROU ADM1
sau limitele ANCPI convertite în EPSG:4326. Județul se recunoaște din prima proprietate care conține un cod
auto („DJ”) sau un nume („Dolj”, „Județul Dolj”). Fișierul nu intră în repo (e mare).
Fără contururi, harta folosește reședința de județ ca punct.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import comun
from db import conecteaza


def judet_din_proprietati(props: dict) -> str | None:
    for cheie in ("cod", "judet", "mnemonic", "shapeISO", "iso", "name", "nume", "shapeName", "NAME_1"):
        v = props.get(cheie)
        if isinstance(v, str):
            cod = comun.cod_judet(v.removeprefix("RO-"))
            if cod:
                return cod
    for v in props.values():
        if isinstance(v, str) and (cod := comun.cod_judet(v.removeprefix("RO-"))):
            return cod
    return None


def importa(conn, cale: Path) -> tuple[int, list[str]]:
    obj = json.loads(cale.read_text(encoding="utf-8"))
    necunoscute, incarcate = [], 0
    with conn.transaction():
        for f in obj.get("features", []):
            cod = judet_din_proprietati(f.get("properties") or {})
            if not cod:
                necunoscute.append(json.dumps(f.get("properties"), ensure_ascii=False)[:80])
                continue
            conn.execute(
                "UPDATE judete SET contur = ST_Multi(ST_CollectionExtract(ST_MakeValid("
                " ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 3)) WHERE cod = %s",
                (json.dumps(f["geometry"]), cod))
            incarcate += 1
    return incarcate, necunoscute


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("geojson", type=Path)
    p.add_argument("--dsn", help="adresa bazei (altfel DATABASE_URL)")
    args = p.parse_args(argv)
    with conecteaza(args.dsn) as conn:
        n, necunoscute = importa(conn, args.geojson)
        lipsa = [r[0] for r in conn.execute("SELECT cod FROM judete WHERE contur IS NULL ORDER BY cod")]
    for x in necunoscute:
        print(f"AVERTISMENT n-am recunoscut județul din {x}")
    print(f"OK: {n} contururi încărcate." + (f" Fără contur: {', '.join(lipsa)}" if lipsa else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
