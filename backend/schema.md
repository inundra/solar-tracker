# Schema bazei de date

**Versiune:** 003 (26 noiembrie 2026) · Issue: #13, #16 · SQL: [`001_schema_initiala.sql`](sql/migrari/001_schema_initiala.sql), [`002_detect_first.sql`](sql/migrari/002_detect_first.sql), [`003_atr_pif.sql`](sql/migrari/003_atr_pif.sql)

PostgreSQL 16 + PostGIS 3. Toate geometriile sunt în WGS84 (EPSG:4326). Formatul CSV-urilor de la Setul de adevăr e în [`validare/schema_csv.md`](../validare/schema_csv.md) (#14).

```
stadii ◄──────────────┬──────────────────┬───────────────────┐
                      │                  │                   │
parcuri (parc_id) ◄── stadii_adevar ──── stadii_pipeline ──► observatii
     ▲                (parc_id, luna)    (parc_id, luna,     (o imagine
     │                                    versiune_model)     pe parc)
     └──────────────────────────────────────────────────────────┘
```

| Tabel | O linie = | Cheie | Cine scrie |
|---|---|---|---|
| `stadii` | un stadiu permis | `cod` | migrarea (fix) |
| `parcuri` | un parc solar | `parc_id` | importul CSV, din `parcuri.csv` |
| `stadii_adevar` | stadiul unui parc într-o lună, stabilit manual | (`parc_id`, `luna`) | importul CSV, din `stadii_lunare.csv` |
| `observatii` | o imagine satelitară analizată pentru un parc | `id`; unic (`parc_id`, `sursa_imagine`, `id_imagine`, `versiune_pipeline`) | pipeline-ul |
| `stadii_pipeline` | stadiul prezis pentru un parc într-o lună | (`parc_id`, `luna`, `versiune_model`) | pipeline-ul |
| `importuri` | o rulare a importului pentru un fișier | `id` | importul CSV |
| `schema_migrari` | o migrare aplicată | `fisier` | `migreaza.py` |

## `stadii`

| Cod | Ordine | Stadiul în produs |
|---|---|---|
| `teren_gol` | 0 | neînceput |
| `santier` | 1 | în construcție |
| `panouri` | 2 | în construcție |
| `gata` | 3 | construit |
| `nesigur` | – | nesigur |

`stadii_adevar`, `stadii_pipeline` și `parcuri.stadiu_curent` fac referire la tabelul ăsta, deci baza refuză orice altă valoare.

## `parcuri`

Coloanele din `parcuri.csv`, cu trei diferențe:

- `lat` și `lon` devin `geom` (punct). Le citiți înapoi din `v_parcuri`.
- `poligon` (MultiPolygon) se încarcă din `validare/proiecte_cartate/<parc_id>.geojson`, dacă fișierul există. Mai multe poligoane în același fișier se unesc.
- `are_poligon` nu se salvează: se vede din `poligon IS NOT NULL`.

În plus: `creat_la`, `actualizat_la` (se schimbă doar când linia chiar s-a schimbat la import).

Reguli verificate de bază: format `parc_id` (`DJ-001`), cod de județ de 1–2 litere, `rol` ∈ {`track`, `check`, `test`, `lista`}, MW ≥ 0, `sursa_mw` obligatorie dacă există `mwp` sau `mwac`, `cui` doar cifre.

## `stadii_adevar`

Coloanele din `stadii_lunare.csv`. `luna` e salvată ca dată, prima zi a lunii (`2025-03` → `2025-03-01`). Baza verifică la fel ca scriptul de validare: imaginea e obligatorie dacă stadiul nu e `nesigur`, iar `data_imagine` trebuie să cadă în `luna`.

## `observatii` (pipeline)

| Coloană | Tip | Note |
|---|---|---|
| `parc_id` | text | |
| `data_imagine` | dată | |
| `sursa_imagine` | text | aceleași valori ca în CSV (`sentinel-2`, `sentinel-1`, …) |
| `id_imagine` | text | numele produsului (ex. `S2B_MSIL2A_...`), ca dovada să poată fi regăsită |
| `cer_senin` | 0–1 | Cloud Score+ pe poligonul parcului |
| `indici` | jsonb | orice valori calculate, ex. `{"ndvi_median": 0.21, "vh_db": -14.2}` |
| `versiune_pipeline` | text | ex. `v0.1` sau hash-ul commit-ului |

## `stadii_pipeline` (pipeline)

| Coloană | Tip | Note |
|---|---|---|
| `parc_id`, `luna` | | aceeași cheie ca `stadii_adevar` |
| `versiune_model` | text | permite compararea mai multor versiuni |
| `stadiu` | text | din `stadii` |
| `incredere` | 0–1 | |
| `mwp_estimat`, `mwp_min`, `mwp_max` | zecimal | MWp ca valoare și interval |
| `suprafata_panouri_ha` | zecimal | |
| `observatie_id` | id | imaginea pe care s-a decis (dovada din raport) |

## Vederi

- `v_parcuri`: parcurile cu `lat`, `lon`, `suprafata_ha` (din poligon) și `stadiu_produs`. Pentru hartă (#16) și pagina de proiect.
- `v_comparatie_stadii`: setul de adevăr lângă predicția pipeline-ului, pe parc, lună și versiune, cu `corect` = true/false. Pentru metricile de validare.

## Planul detect-first (migrarea 002)

Lista ATR a Guvernului dă doar județul, nu amplasamentul (vezi [`docs/decizii/2026-11-26_detect-first.md`](../docs/decizii/2026-11-26_detect-first.md)). De aceea pornim de la ce se vede din satelit (detecții) și le legăm apoi de ATR-uri.

```
judete ◄── atr ──► companii (cui)          parcuri (setul de adevăr)
  ▲         ▲                                  ▲
  │         │ legaturi_atr (propusa / confirmata / respinsa)
  │         │                                  │
  └──── detectii ◄── jurnal_detectii           │
          └──────────── parc_id ───────────────┘
```

| Tabel | O linie = | Cheie | Cine scrie |
|---|---|---|---|
| `judete` | un județ (cod auto, nume, reședință, contur opțional) | `cod` | migrarea; conturul cu `importa_judete.py` |
| `companii` | un titular de ATR | `cui` | `importa_atr.py` |
| `atr` | un aviz tehnic de racordare | `id`; unic (`numar`, `titular`, `judet`) | `importa_atr.py` |
| `detectii` | un parc sau șantier găsit pe imagini | `detectie_id` | `importa_detectii.py` (pipeline, TZ-SAM, OSM, manual) |
| `jurnal_detectii` | o imagine pe care s-a văzut stadiul unei detecții | `id`; unic (`detectie_id`, `sursa_imagine`, `id_imagine`, `versiune_pipeline`) | `importa_detectii.py` |
| `legaturi_atr` | o pereche detecție ↔ ATR | (`detectie_id`, `atr_id`) | `leaga_atr.py` |
| `parametri` | o constantă folosită în vederi | `cheie` | migrarea; se schimbă cu `UPDATE` |

`parcuri.judet` face acum referire la `judete.cod`.

### `atr`

| Coloană | Tip | Note |
|---|---|---|
| `numar`, `data_atr` | text, dată | numărul și data avizului |
| `titular`, `cui` | text | `cui` → `companii` |
| `judet` | cod | singura locație din lista publică |
| `mw` | zecimal | puterea aprobată (AC) |
| `operator`, `etapa`, `data_pif` | | operatorul de rețea, etapa din listă, data estimată de punere în funcțiune |
| `tehnologie` | text | `fotovoltaic`, `stocare`, `hibrid`, `eolian`, `alta`, `necunoscuta`; ghicită din titular dacă lipsește |
| `localitate` | text | completată manual (APM, primării) sau din detecția confirmată |
| `sursa` | text | URL-ul listei sau al documentului |
| `pif_text` | text | celula PIF exact cum e în listă (migrarea 003) |
| `stare_pif`, `an_pif` | text, an | `estimat`, `realizat`, `anulat`, `retehnologizat`, `necunoscut`; anul, chiar și fără dată completă |
| `judete_secundare` | text[] | celelalte județe, pentru ATR-urile pe mai multe județe |
| `reparat` | bool | o celulă a fost corectată la import (detaliile în `note`) |

CSV-ul de intrare pentru `importa_atr.py`: `numar_atr, data_atr, titular, cui, judet, mw, operator, etapa, data_pif, tehnologie, localitate, sursa, note`. Obligatorii: `numar_atr`, `titular`, `judet`, `mw`. Exemplu: [`date_brute/exemplu_atr.csv`](date_brute/exemplu_atr.csv). Din PDF-ul Guvernului se obține cu `extrage_atr_pdf.py`.

### `detectii` și `jurnal_detectii`

| Coloană | Note |
|---|---|
| `detectie_id` | dat de pipeline, stabil între rulări (ex. `DJ-2026-0007`) |
| `sursa` | `pipeline`, `tz-sam`, `osm`, `manual` (în ordinea priorității la duplicate: `manual` > `pipeline` > `tz-sam` > `osm`) |
| `judet`, `uat` | județul e obligatoriu (din GeoJSON sau din conturul județelor) |
| `poligon` | MultiPolygon WGS84 |
| `tip` | `fotovoltaic`, `stocare`, `necunoscut` |
| `stadiu_curent`, `data_stadiu` | stadiul și imaginea pe care s-a decis |
| `data_defrisare`, `data_module` | prima imagine cu șantier și prima cu panouri (din jurnal, dacă lipsesc) |
| `mwp_estimat`, `mwp_min`, `mwp_max` | din pipeline; dacă lipsesc, vederea le estimează din suprafață × `parametri.mwp_pe_ha` |
| `parc_id` | parcul din setul de adevăr peste care cade detecția (completat automat la import) |
| `duplicat_al` | aceeași instalație găsită de o sursă cu prioritate mai mare (IoU ≥ 0,3); nu se numără de două ori |

Jurnalul ține dovezile: `data_imagine`, `stadiu`, `sursa_imagine`, `id_imagine` (produsul), `tile`, `cer_senin`, `suprafata_ha`, `versiune_pipeline`.

### Contract: detecții de la pipeline

Pipeline Satelitar predă un GeoJSON `FeatureCollection` (WGS84), un `Feature` pe detecție, cu `Polygon` sau `MultiPolygon`. Exemplu complet: [`date_brute/exemplu_detectii.geojson`](date_brute/exemplu_detectii.geojson).

```json
{"type": "Feature",
 "geometry": {"type": "Polygon", "coordinates": [[[23.69, 44.38], [23.71, 44.38], [23.71, 44.40], [23.69, 44.40], [23.69, 44.38]]]},
 "properties": {
   "detectie_id": "DJ-2026-0007", "sursa": "pipeline", "judet": "DJ", "uat": "Ișalnița",
   "stadiu_curent": "panouri", "incredere": 0.8, "mwp_estimat": 31.2, "mwp_min": 26, "mwp_max": 36,
   "versiune_pipeline": "v0.1",
   "jurnal": [
     {"data_imagine": "2025-05-02", "stadiu": "santier", "sursa_imagine": "sentinel-2",
      "id_imagine": "S2B_MSIL2A_20250502T092029_...", "tile": "T34TFQ", "cer_senin": 0.88},
     {"data_imagine": "2025-09-19", "stadiu": "panouri", "sursa_imagine": "sentinel-2",
      "id_imagine": "S2A_MSIL2A_20250919T092031_...", "tile": "T34TFQ", "cer_senin": 0.97, "suprafata_ha": 21.4}
   ]}}
```

Obligatorii: `detectie_id`, `stadiu_curent`, `sursa` (sau `--sursa` la import), `judet` (dacă nu e încărcat conturul județelor). Stadiile sunt aceleași ca în setul de adevăr. Setul TZ-SAM sau OSM se importă la fel, cu `--sursa tz-sam` / `--sursa osm`.

Pentru parcurile din setul de adevăr, stadiul prezis lună de lună intră separat, ca CSV, cu `importa_stadii_pipeline.py` (`parc_id, luna, versiune_model, stadiu, incredere, mwp_estimat, mwp_min, mwp_max, suprafata_panouri_ha, sursa_imagine, data_imagine, id_imagine, cer_senin`), ca să poată fi comparat cu adevărul în `v_comparatie_stadii`.

### `legaturi_atr`

`leaga_atr.py propune` scrie candidații (`propusa`) pentru detecțiile fără ATR confirmat: ATR-urile din același județ, cu tehnologie compatibilă, cu scor ≥ 0,35 (MW 55%, localitate în numele titularului 35%, dată 10%; CUI identic cu al parcului = 1). Un om confirmă sau respinge (`decis_de` obligatoriu). O detecție are cel mult un ATR confirmat; candidații respinși nu mai sunt propuși.

### Vederi noi

- `v_detectii`: detecțiile cu `lat`, `lon`, `suprafata_ha`, `mwp` (+ interval), `stadiu_produs` și ATR-ul confirmat.
- `v_atr`: fiecare ATR cu detecția confirmată și `stare_teren` (`fara_santier_legat`, `santier`, `panouri`, `gata`, ...).
- `v_judete`: harta națională, pe județ: `nr_atr`, `mw_aprobat` (total, fotovoltaic, stocare), `mwp_construit`, `mwp_in_constructie`, `nr_santiere`, `nr_legate_de_atr`, `procent_vizibil_pe_teren` = (construit + în construcție) / `dc_ac` / aprobat. Duplicatele nu se numără.

### `parametri`

| Cheie | Valoare | Folosită la |
|---|---|---|
| `mwp_pe_ha` (`_min`, `_max`) | 0,70 (0,50–0,90) | MWp estimați din suprafața gardului, când pipeline-ul nu dă MWp |
| `dc_ac` | 1,20 | conversia MWp (DC) → MW din ATR (AC) |

Valorile sunt aproximări de pornire; echipa de validare le poate corecta pe parcurile CHECK (`UPDATE parametri SET valoare = ... WHERE cheie = ...`).

## Ce urmează

CfD și tranzacțiile, legate de `companii` și `atr`, într-o migrare `004_...`.

Schema se schimbă doar printr-o migrare nouă (`004_...sql`); migrările deja aplicate nu se editează.
