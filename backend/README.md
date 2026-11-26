# Date / Backend

**Responsabil:** echipa Date / Backend

Baza de date PostgreSQL + PostGIS, importurile și API-ul cu harta MWitness. Tabelele sunt descrise în [`schema.md`](schema.md).

Lucrăm pe planul **detect-first** ([decizia](../docs/decizii/2026-11-26_detect-first.md)): lista ATR a Guvernului dă doar județul, deci pornim de la parcurile și șantierele detectate din satelit și le legăm apoi de ATR-uri. Harta națională compară, pe fiecare județ, MW aprobați cu MWp construiți.

## Structură

- `sql/migrari/`: scripturi SQL numerotate (`001_...`, `002_...`), aplicate în ordine de `src/migreaza.py`.
- `src/`:
  - `migreaza.py`: aplică migrările care lipsesc.
  - `importa_csv.py`: setul de adevăr, `validare/parcuri.csv` și `validare/stadii_lunare.csv` (#15).
  - `extrage_atr_pdf.py`: tabelul din PDF-ul Guvernului cu ATR-uri → CSV.
  - `importa_atr.py`: ATR-urile și companiile (CUI).
  - `importa_judete.py`: conturul județelor (opțional).
  - `importa_detectii.py`: detecțiile de la pipeline (sau TZ-SAM / OSM) și jurnalul lor de dovezi.
  - `importa_stadii_pipeline.py`: stadiul prezis lună de lună pentru parcurile din setul de adevăr (pentru validare).
  - `leaga_atr.py`: propune ATR-uri candidate pentru fiecare detecție; un om le confirmă sau le respinge.
  - `api.py` + `raport.py`: API-ul (FastAPI), harta și rapoartele de dovezi (#16).
- `web/harta.html`: harta (Leaflet), servită de API la `/`.
- `teste/`: teste pe o bază reală.
- `date_brute/`: doar fișiere mici: exemplele (inventate) și CSV-ul extras din lista ATR. Datele mari nu intră în repo.

## Pornire rapidă

```bash
# 1. Baza locală (sau un PostgreSQL cu PostGIS deja instalat)
docker compose -f backend/docker-compose.yml up -d

# 2. Dependențe și conexiune
pip install -r backend/requirements.txt
cp backend/.env.exemplu backend/.env      # editați DATABASE_URL dacă e nevoie

# 3. Schema
python backend/src/migreaza.py

# 4. Datele, în ordinea asta
python backend/src/importa_csv.py                                   # setul de adevăr (validare/)
python backend/src/extrage_atr_pdf.py Lista_titularilor_care_detin_ATR.pdf backend/date_brute/atr_guvern_2026.csv
python backend/src/importa_atr.py backend/date_brute/atr_guvern_2026.csv
python backend/src/importa_detectii.py <detectii_pipeline>.geojson  # de la Pipeline Satelitar
python backend/src/leaga_atr.py propune

# 5. API și harta
uvicorn api:app --app-dir backend/src --reload
# harta: http://localhost:8000/    documentația API: http://localhost:8000/docs
```

Ca să vedeți totul funcționând fără date reale, folosiți exemplele (valori inventate):

```bash
python backend/src/importa_csv.py --parcuri validare/exemplu_parcuri.csv --stadii validare/exemplu_stadii_lunare.csv
python backend/src/importa_atr.py backend/date_brute/exemplu_atr.csv
python backend/src/importa_detectii.py backend/date_brute/exemplu_detectii.geojson
python backend/src/leaga_atr.py propune && python backend/src/leaga_atr.py lista
```

Toate importurile validează întâi fișierul și, la orice eroare, nu scriu nimic. Scriu totul într-o singură tranzacție, pot fi rulate de câte ori vreți fără duplicate și notează fiecare rulare în tabelul `importuri`. Cu `--verifica`, simulează importul fără să scrie.

## Lista ATR a Guvernului

PDF-ul: <https://gov.ro/fisiere/stiri_fisiere/Lista_titularilor_care_detin_ATR.pdf> (aprilie–mai 2026, date de la Transelectrica). `extrage_atr_pdf.py` recunoaște tabelul după antet (titular, CUI, județ, MW, operator, etapă, PIF), indiferent de ordinea coloanelor, și desparte „Nr. și dată ATR” dacă sunt în aceeași celulă. Verificați câteva linii din CSV cu PDF-ul înainte de import. PDF-ul nu intră în repo; CSV-ul da, în `date_brute/`.

## Legarea detecțiilor de ATR-uri

```bash
python backend/src/leaga_atr.py propune --judet DJ
python backend/src/leaga_atr.py lista --judet DJ
python backend/src/leaga_atr.py confirma DJ-2026-0007 412 --de <login-github> --note "APM Dolj, anunț 2025"
python backend/src/leaga_atr.py respinge DJ-2026-0007 398 --de <login-github>
```

Scorul se bazează pe județ, MW (MWp detectați comparați cu MW din ATR), localitatea detecției în numele titularului și data ATR-ului. E doar o propunere: pentru cele 30 de proiecte din livrabil, legătura se confirmă manual, cu sursa (APM, primărie, presă) în `--note`.

## API

| Ruta | Ce dă |
|---|---|
| `GET /` | harta |
| `GET /api/judete` | GeoJSON, pe județ: MW aprobați, MWp construiți și în construcție, % vizibil pe teren |
| `GET /api/detectii?judet=&stadiu=&sursa=` | GeoJSON cu detecțiile |
| `GET /api/detectii/{id}` | o detecție, cu jurnalul de imagini și ATR-urile candidate |
| `GET /api/detectii/{id}/raport` | raportul de dovezi datat (Markdown) |
| `GET /api/parcuri?judet=&rol=` | GeoJSON cu parcurile din setul de adevăr |
| `GET /api/parcuri/{parc_id}` și `/raport` | stadiile lunare (adevăr și pipeline) și raportul |
| `GET /api/atr?q=&cui=&judet=&stare_teren=` | căutare ATR după titular, număr, CUI sau județ |
| `GET /api/companii/{cui}` | o companie și toate ATR-urile ei |
| `GET /api/sanatate` | câte înregistrări are fiecare tabel |

## Teste

Pe o bază separată, care se golește la fiecare test:

```bash
TEST_DATABASE_URL=postgresql://mwitness:mwitness@localhost:5432/mwitness_test \
    python -m unittest discover -s backend/teste -v
```

Conexiunea la baza de date se configurează prin variabile de mediu (`.env`, care nu se urcă în repo).
