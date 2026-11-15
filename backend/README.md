# Date / Backend

**Responsabil:** echipa Date / Backend

Baza de date PostgreSQL + PostGIS cu parcurile solare, stadiile lunare din setul de adevăr și rezultatele pipeline-ului satelitar. Tabelele sunt descrise în [`schema.md`](schema.md).

Mai târziu: ATR-uri, companii (CUI), CfD și tranzacții, legate de parcuri.

## Structură

- `sql/migrari/`: scripturi SQL numerotate (`001_schema_initiala.sql`, `002_...`), aplicate în ordine de `src/migreaza.py`.
- `src/`: cod Python pentru import și curățare.
  - `migreaza.py`: aplică migrările care lipsesc.
  - `importa_csv.py`: importă `validare/parcuri.csv` și `validare/stadii_lunare.csv` (#15).
- `teste/`: teste pe o bază reală.
- `date_brute/`: doar fișiere mici de exemplu; datele mari nu intră în repo.

## Pornire rapidă

```bash
# 1. Baza locală (sau folosiți un PostgreSQL cu PostGIS deja instalat)
docker compose -f backend/docker-compose.yml up -d

# 2. Dependențe și conexiune
pip install -r backend/requirements.txt
cp backend/.env.exemplu backend/.env      # editați DATABASE_URL dacă e nevoie

# 3. Schema
python backend/src/migreaza.py

# 4. Importul CSV-urilor de la Setul de adevăr
python backend/src/importa_csv.py
```

`importa_csv.py`:

- validează întâi fișierele cu `validare/valideaza_csv.py`; la orice eroare nu scrie nimic;
- scrie totul într-o singură tranzacție;
- poate fi rulat de câte ori vreți: parcurile se actualizează după `parc_id`, stadiile după (`parc_id`, `luna`), fără duplicate;
- încarcă poligoanele din `validare/proiecte_cartate/<parc_id>.geojson`;
- notează fiecare rulare în tabelul `importuri` (fișier, hash, câte linii noi / actualizate / neschimbate).

Opțiuni utile: `--parcuri` și `--stadii` (alte fișiere, ex. exemplele din `validare/`), `--verifica` (simulare, nu scrie nimic), `--sterge-lipsa` (șterge stadiile care nu mai sunt în CSV).

## Teste

Pe o bază separată, care se golește la fiecare test:

```bash
TEST_DATABASE_URL=postgresql://mwitness:mwitness@localhost:5432/mwitness_test \
    python -m unittest discover -s backend/teste -v
```

Conexiunea la baza de date se configurează prin variabile de mediu (`.env`, care nu se urcă în repo).
