"""Conexiunea la PostgreSQL, comună scripturilor din backend/src.

Adresa bazei vine din variabila de mediu DATABASE_URL (sau din backend/.env),
de exemplu: postgresql://mwitness:mwitness@localhost:5432/mwitness
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent


def citeste_env(cale: Path = BACKEND / ".env") -> None:
    """Încarcă variabilele din backend/.env, fără să le suprascrie pe cele deja setate."""
    if not cale.exists():
        return
    for linie in cale.read_text(encoding="utf-8").splitlines():
        linie = linie.strip()
        if not linie or linie.startswith("#") or "=" not in linie:
            continue
        cheie, valoare = linie.split("=", 1)
        os.environ.setdefault(cheie.strip(), valoare.strip().strip("'\""))


def conecteaza(dsn: str | None = None) -> psycopg.Connection:
    citeste_env()
    dsn = dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("Lipsește DATABASE_URL (setați-o în mediu sau în backend/.env; vedeți .env.exemplu).")
    return psycopg.connect(dsn)
