# Solar Park Construction Tracker

Proiectul echipei Inundra pentru Rospin Data Processing Masterclass (Earth Observation & Geospatial ML).

## Ce construim

Un sistem care urmărește parcurile fotovoltaice din România din imagini satelitare:

1. **Segmentare** pe Sentinel-2: unde apare un parc solar și ce suprafață ocupă.
2. **Stadiul construcției**: teren pregătit, structuri montate, panouri instalate, parc finalizat.
3. **Legătura cu datele administrative**: fiecare parc detectat este asociat cu avizul tehnic de racordare (ATR), compania dezvoltatoare (CUI) și amplasamentul.

**Cui îi folosește:** dezvoltatori de proiecte, traderi de energie, bănci care finanțează proiecte, Transelectrica.

## Structura repo-ului

| Folder | Echipa | Ce conține |
|---|---|---|
| [`business/`](business/) | Business | interviuri cu clienți, pitch, Business Model Canvas, video demo |
| [`backend/`](backend/) | Date / Backend | baza de date PostgreSQL + PostGIS: ATR-uri, companii, CUI-uri, amplasamente |
| [`pipeline/`](pipeline/) | Pipeline Satelitar | Earth Engine / openEO, Sentinel-2, Sentinel-1, Cloud Score+ |
| [`validare/`](validare/) | Setul de adevăr și validarea | 30 de proiecte cartate manual, legate de ATR-uri, metrici de validare |
| [`docs/`](docs/) | toată echipa | arhitectură, decizii, note de întâlnire |

Discuțiile generale au loc pe canalul **General**, nu în repo.

## Cum lucrăm

- Fiecare echipă lucrează în folderul ei. Schimbările în folderele altor echipe trec prin pull request cu review de la echipa respectivă.
- Ramuri: `<echipa>/<scurta-descriere>`, de exemplu `pipeline/cloud-score-mask`.
- Nu se urcă în repo date mari (rastere, GeoTIFF, `.zip`), chei API sau fișiere `.env`. Vezi [`.gitignore`](.gitignore).
- Setul de adevăr din `validare/` nu se folosește la antrenare: e păstrat separat pentru evaluare.
- Deciziile importante se notează pe scurt în [`docs/decizii/`](docs/decizii/).

## Pornire rapidă

```bash
git clone https://github.com/inundra/<nume-repo>.git
cd <nume-repo>
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

Fiecare folder are propriul README cu pașii specifici.

## Licență

[MIT](LICENSE)
