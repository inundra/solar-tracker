# Schema bazei de date

**Versiune:** 001 (15 noiembrie 2026) · Issue: #13 · SQL: [`sql/migrari/001_schema_initiala.sql`](sql/migrari/001_schema_initiala.sql)

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

## Ce urmează (migrări noi)

ATR-urile din lista guvernamentală, companiile (CUI), CfD și tranzacțiile vor fi tabele separate legate de `parcuri`, în `002_...`. Până atunci, deținătorul, CUI-ul și ATR-ul stau direct în `parcuri`, cum vin din CSV.

Schema se schimbă doar printr-o migrare nouă (`002_...sql`); migrările deja aplicate nu se editează.
