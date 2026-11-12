# MWitness

Proiectul echipei Inundra pentru Satellite Data Processing Masterclass (Rospin), track Enterprise Software, domeniul Energie și resurse naturale.

MWitness folosește imagini satelitare ca să arate care dintre proiectele solare și de stocare (BESS) aprobate în România se construiesc cu adevărat, cât de avansate sunt și ce putere reală au în MWp, legate de avizul de racordare (ATR), proprietarul și tranzacțiile fiecărui proiect.

## Problema

- România a emis peste 1.400 de ATR-uri, deținute de peste 1.000 de companii: peste 80.000 MW aprobați pe hârtie (aprilie 2026), față de 2.514 MW racordați în 2026.
- Registrele publice dau doar județul, fără locație, și nu spun dacă lucrările au început.
- Ordinul ANRE 15/2026 cere deținătorilor peste 1 MW să obțină autorizația de înființare în 12 luni (termen în jurul lui mai 2027, prelungibil o dată cu până la 12 luni). Testul e doar pe acte: nimeni nu verifică terenul și nu există un registru public cu stadiul lucrărilor. Detalii în [`docs/decizii/2026-11-12_ordin-anre-15-2026.md`](docs/decizii/2026-11-12_ordin-anre-15-2026.md).

Investitorii, echipele de M&A, traderii și consultanții tehnici ai băncilor nu au o sursă independentă despre ce se întâmplă pe teren. MWitness o oferă.

## Ce face

- Caută un proiect după proprietar, CUI sau județ.
- Îl arată pe hartă, cu imagini satelitare datate.
- Dă stadiul: `neînceput`, `în construcție`, `construit` sau `nesigur` (când imaginile nu sunt concludente).
- Estimează MWp din suprafața panourilor și un interval de MWac.
- Leagă actele (ATR, CfD, tranzacții) și exportă un raport de dovezi datat.

## Livrabile la 11 decembrie 2026

1. Hartă națională cu totaluri pe județ: aprobat față de construit.
2. 30 de proiecte legate manual, fiecare cu pagină proprie și time-lapse Sentinel-2.
3. Defrișarea terenului și modulele finalizate, detectate și datate, cu categoria `nesigur`.
4. Jurnal de modificări al dovezilor (data imaginii, produs, tile).

Mai târziu: MWp și stadiul pilonilor din imagini VHR plătite, numărarea containerelor BESS, Build-out Feed pentru traderi, radar de termene.

## Zone de studiu

| Rol | Județe | Parcuri | La ce folosește |
|---|---|---|---|
| TRACK | Dolj, Gorj | Tismana, Rovinari, Ișalnița | parcuri în construcție acum: urmărim progresul |
| CHECK | Dâmbovița, Giurgiu | Văcărești, Titu | parcuri terminate, cu MWp și date cunoscute: verificăm modelul |

Validarea se face leave-one-park-out: modelul e evaluat pe un parc pe care nu l-a văzut la antrenare.

## Date

| Sursă | Rezoluție | Revizitare | Acces | Folosit pentru |
|---|---|---|---|---|
| Sentinel-2 L2A | 10 m (RGB, NIR), 20 m (SWIR) | 2–3 zile | CDSE, Earth Engine | defrișare și module, cu date |
| Sentinel-1 GRD | 10 m, VV + VH | 6 zile | CDSE, Earth Engine | detectarea schimbărilor în săptămânile cu nori |
| Cloud Score+ | 10 m | la fiecare scenă S2 | Earth Engine | mască de nori, scor de cer senin ≥ 0,60 |

Date administrative: lista guvernamentală de ATR-uri (deținător, CUI, MW, județ, etapă), rapoartele de racordare Transelectrica, Ordinul ANRE 15/2026, rezultatele licitațiilor CfD, MWp raportat de dezvoltatori (pentru validare).

## Plan de lucru

| Săptămâna | Perioada | Ce se lucrează |
|---|---|---|
| 1 | 7–13 nov | acces la date: ATR, Sentinel, arhivă |
| 2 | 14–20 nov | pipeline de filtrare Sentinel-1/2; încep modelul de stadiu și MWp |
| 3 | 21–27 nov | model de stadiu și MWp; hartă și pagini de proiect; prezentarea intermediară (data se confirmă) |
| 4 | 28 nov–4 dec | validare (MWp, leave-one-park-out); pitch și analiză de business |
| 5 | 5–11 dec | README, video demo, predare pe 11 decembrie |

## Riscuri și plan B

| Risc | Plan B |
|---|---|
| Legarea ATR-urilor de amplasamente durează prea mult | limităm demo-ul la 30 de proiecte și parcuri ≥ 10 MWac |
| Sentinel-2 nu estimează MWp la ±8% | raportăm MWp ca interval; vindem stadiul și datele |
| Niciun client nu plătește peste datele gratuite | 10 interviuri înainte de 11 decembrie; resegmentăm dacă testul de disponibilitate de plată (V6) eșuează |

## Structura repo-ului

| Folder | Echipa | Ce conține |
|---|---|---|
| [`business/`](business/) | Business | interviuri cu clienți, pitch, Business Model Canvas, video demo |
| [`backend/`](backend/) | Date / Backend | PostgreSQL + PostGIS: ATR-uri, companii, CUI-uri, amplasamente, CfD, tranzacții |
| [`pipeline/`](pipeline/) | Pipeline Satelitar | Earth Engine / openEO, Sentinel-2, Sentinel-1, Cloud Score+, stadiu și MWp |
| [`validare/`](validare/) | Setul de adevăr și validarea | 30 de proiecte cartate manual, legate de ATR-uri, metrici de validare |
| [`docs/`](docs/) | toată echipa | arhitectură, decizii, note de întâlnire |

## Cum lucrăm

- Fiecare echipă lucrează în folderul ei. Schimbările în folderele altor echipe trec prin pull request cu review de la echipa respectivă.
- Ramuri: `<echipa>/<scurta-descriere>`, de exemplu `pipeline/cloud-score-mask`.
- Nu se urcă în repo date mari (rastere, GeoTIFF, `.zip`), chei API sau fișiere `.env`. Vezi [`.gitignore`](.gitignore).
- Setul de adevăr din `validare/` nu se folosește la antrenare: e păstrat separat pentru evaluare.
- Deciziile importante se notează pe scurt în [`docs/decizii/`](docs/decizii/).

## Echipa Inundra

Alexandru Achille Flueraru (team lead), Rareș Rolea, Denis Andrei Robu, Gabriel Dobrin, Andrei Mănescu, Rareș Păun Bogdan, Silvius Suchea.

## Pornire rapidă

```bash
git clone https://github.com/inundra/solar-tracker.git
cd solar-tracker
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

Fiecare folder are propriul README cu pașii specifici.

## Licență

[MIT](LICENSE)
