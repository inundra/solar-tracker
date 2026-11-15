# Schema CSV comună: Setul de adevăr ↔ Date/Backend

**Versiune:** 0.1 (propunere, 13 noiembrie 2026) · Issue: #14

Setul de adevăr predă două fișiere CSV, pe care Date/Backend le importă direct în baza de date (#15):

| Fișier | O linie = | Folosit în |
|---|---|---|
| `validare/parcuri.csv` | un parc solar | #6 (lista de 20–30 de parcuri), #13, #15, #16 |
| `validare/stadii_lunare.csv` | un parc într-o lună | #7 (stadiul lună de lună), #11, #12, validare |

Poligoanele nu intră în CSV. Fiecare parc cartat are un fișier GeoJSON în `validare/proiecte_cartate/<parc_id>.geojson` (vezi mai jos).

Exemple complete: [`exemplu_parcuri.csv`](exemplu_parcuri.csv) și [`exemplu_stadii_lunare.csv`](exemplu_stadii_lunare.csv). Valorile din exemple sunt inventate, nu sunt parcuri reale.

Verificare: `python validare/valideaza_csv.py validare/parcuri.csv validare/stadii_lunare.csv`

## Reguli de format

- Codare UTF-8, separator virgulă (`,`), punct zecimal (`45.12`, nu `45,12`), prima linie e antetul.
- Din Excel: „Salvare ca” → **CSV UTF-8 (delimitat prin virgulă)**. Excelul în limba română poate pune `;` și virgulă zecimală: verificați cu scriptul înainte de commit.
- Numele coloanelor sunt exact cele de mai jos (litere mici, fără diacritice), în orice ordine. Coloanele în plus sunt semnalate ca avertisment, nu ca eroare.
- Celulă goală = valoare necunoscută. Nu scrieți `-`, `N/A` sau `?`.
- Date calendaristice: `AAAA-LL-ZZ` (ex. `2026-11-13`). Luni: `AAAA-LL` (ex. `2025-03`).
- Textele care conțin virgulă se pun între ghilimele (Excel face asta singur).

## Valori permise pentru stadiu

Aceleași valori în ambele fișiere (`stadiu_curent` și `stadiu`):

| Valoare | Ce se vede în imagine | Stadiul în produs (README) |
|---|---|---|
| `teren_gol` | teren agricol, pășune sau teren viran; nicio lucrare | `neînceput` |
| `santier` | teren decopertat sau nivelat, drumuri de șantier, piloni, utilaje; fără panouri | `în construcție` |
| `panouri` | panouri montate pe o parte din suprafață (sub ~90%) | `în construcție` |
| `gata` | panouri pe toată suprafața, șantier strâns; parcul pare terminat | `construit` |
| `nesigur` | imaginile nu permit o decizie (nori, rezoluție, nicio imagine în lună) | `nesigur` |

Reguli:

- Stadiile urmează ordinea `teren_gol` → `santier` → `panouri` → `gata`. Un pas înapoi de la o lună la alta (fără `nesigur` între ele) e semnalat ca avertisment: poate fi o greșeală sau o extindere a parcului, caz în care se explică în `note`.
- `gata` înseamnă construit vizibil, nu racordat. Data racordării, dacă e cunoscută, se trece în `note`.

## `parcuri.csv`

| Coloană | Tip | Obligatoriu | Valori / exemplu | Note |
|---|---|---|---|---|
| `parc_id` | text | da | `DJ-001` | codul județului + număr din 3 cifre; unic; nu se schimbă niciodată |
| `nume` | text | da | `Parc fotovoltaic Exemplu Nord` | numele folosit în presă sau de dezvoltator |
| `judet` | text | da | `DJ` | cod auto de județ (lista din script); `B` pentru București |
| `uat` | text | nu | `Ișalnița` | comuna/orașul, cu diacritice |
| `lat` | zecimal | da | `44.391234` | WGS84 (EPSG:4326), centrul parcului, 5–6 zecimale; între 43.6 și 48.3 |
| `lon` | zecimal | da | `23.712345` | WGS84, între 20.2 și 29.8 |
| `are_poligon` | `da` / `nu` | da | `da` | `da` dacă există `proiecte_cartate/<parc_id>.geojson` |
| `mwp` | zecimal | nu | `45.2` | putere instalată în panouri (DC) |
| `mwac` | zecimal | nu | `38` | putere la racordare (AC), dacă e cunoscută separat |
| `sursa_mw` | text | dacă există `mwp` sau `mwac` | URL sau „comunicat dezvoltator 2025-04” | de unde vine puterea |
| `detinator` | text | nu | `Exemplu Solar SRL` | firma care deține proiectul/ATR-ul |
| `cui` | număr | nu | `12345678` | fără prefixul `RO`, 2–10 cifre |
| `atr_numar` | text | nu | `ATR 123/2023` | numărul avizului tehnic de racordare |
| `atr_data` | dată | nu | `2023-05-17` | data emiterii ATR |
| `atr_mw` | zecimal | nu | `40` | puterea aprobată în ATR (MW) |
| `rol` | text | da | `track` | `track` (în construcție, urmărim), `check` (terminat, cu MWp și date cunoscute), `test` (parcul de test din #8), `lista` (restul) |
| `stadiu_curent` | stadiu | da | `santier` | stadiul la `data_verificare` |
| `data_verificare` | dată | da | `2026-11-13` | când ați verificat stadiul curent |
| `sursa` | text | da | URL | de unde știm de parc (ATR/ANRE, presă, Transelectrica) |
| `verificat_de` | text | da | `AlexandruAchilleF` | login GitHub al celui care a completat linia |
| `note` | text | nu | | orice altceva |

## `stadii_lunare.csv`

O linie pentru fiecare parc și lună, ianuarie 2024 – luna curentă. Cheia este perechea (`parc_id`, `luna`): nu pot exista două linii cu aceeași pereche. Importul din #15 suprascrie linia existentă, deci fișierul poate fi reimportat fără duplicate.

| Coloană | Tip | Obligatoriu | Valori / exemplu | Note |
|---|---|---|---|---|
| `parc_id` | text | da | `DJ-001` | trebuie să existe în `parcuri.csv` |
| `luna` | lună | da | `2025-03` | între `2024-01` și luna curentă |
| `stadiu` | stadiu | da | `panouri` | vezi tabelul de stadii |
| `sursa_imagine` | text | da, dacă stadiul nu e `nesigur` | `sentinel-2` | `sentinel-2`, `sentinel-1`, `google-earth`, `planet`, `ortofoto`, `alta` |
| `data_imagine` | dată | da, dacă stadiul nu e `nesigur` | `2025-03-14` | data imaginii pe care ați decis; trebuie să cadă în `luna` |
| `id_imagine` | text | nu | `S2B_MSIL2A_20250314T092029_...` | numele produsului sau linkul, ca dovada să poată fi regăsită |
| `verificat_de` | text | da | `AlexandruAchilleF` | login GitHub |
| `note` | text | nu | | ex. „30% nori”, „extindere spre est” |

Lunile fără nicio imagine utilizabilă se trec cu `nesigur` și `sursa_imagine` gol, ca să se vadă că luna a fost verificată.

## Poligoane (`validare/proiecte_cartate/`)

- Un fișier pe parc: `<parc_id>.geojson`, de exemplu `DJ-001.geojson`.
- WGS84 (EPSG:4326), un `Polygon` sau `MultiPolygon` care urmează gardul parcului.
- `properties` conține cel puțin `parc_id`, `sursa_imagine`, `data_imagine` (imaginea pe care s-a desenat) și `cartat_de`.

## Cum ajung datele în baza de date (pentru #13 și #15)

| CSV | Tabel (propunere) | Cheie |
|---|---|---|
| `parcuri.csv` | `parcuri` (+ `geom` punct din `lat`/`lon`, `poligon` din GeoJSON) | `parc_id` |
| `stadii_lunare.csv` | `stadii_adevar` | (`parc_id`, `luna`) |

Rezultatele pipeline-ului (stadiu prezis pe lună) folosesc aceleași valori de stadiu și aceeași cheie (`parc_id`, `luna`), ca să se poată compara direct cu setul de adevăr.

## Schimbări

Schema se schimbă doar prin pull request cu review de la ambele echipe. Creșteți versiunea de sus și notați schimbarea aici.

- 0.1 (2026-11-13): propunerea inițială.
