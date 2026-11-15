"""Aplică migrările din backend/sql/migrari/ în ordine, o singură dată fiecare.

Folosire:
    python backend/src/migreaza.py            # aplică ce lipsește
    python backend/src/migreaza.py --status   # arată ce e aplicat

Fiecare fișier rulează într-o tranzacție separată; numele lui se notează în tabelul schema_migrari.
"""

from __future__ import annotations

import argparse
import sys

from db import BACKEND, conecteaza

MIGRARI = BACKEND / "sql" / "migrari"


def aplica(conn, status: bool = False) -> list[str]:
    with conn.transaction():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrari ("
            " fisier text PRIMARY KEY, aplicata_la timestamptz NOT NULL DEFAULT now())"
        )
    aplicate = {r[0] for r in conn.execute("SELECT fisier FROM schema_migrari")}
    noi = []
    for cale in sorted(MIGRARI.glob("*.sql")):
        if cale.name in aplicate:
            if status:
                print(f"  aplicată  {cale.name}")
            continue
        if status:
            print(f"  lipsește  {cale.name}")
            continue
        with conn.transaction():
            conn.execute(cale.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrari (fisier) VALUES (%s)", (cale.name,))
        print(f"  aplicată acum  {cale.name}")
        noi.append(cale.name)
    return noi


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dsn", help="adresa bazei (altfel DATABASE_URL)")
    p.add_argument("--status", action="store_true", help="doar arată starea, nu aplică nimic")
    args = p.parse_args(argv)
    with conecteaza(args.dsn) as conn:
        noi = aplica(conn, status=args.status)
    if not args.status:
        print(f"OK: {len(noi)} migrări noi." if noi else "OK: baza e la zi.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
