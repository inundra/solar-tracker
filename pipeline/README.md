# Pipeline Satelitar

**Responsabil:** echipa Pipeline Satelitar

- **Surse:** Sentinel-2 (optic), Sentinel-1 (radar, util când e înnorat).
- **Platforme:** Google Earth Engine și/sau openEO.
- **Mască de nori:** Cloud Score+.
- **Ieșiri:** pentru fiecare proiect, stadiul pe date (`neînceput`, `în construcție`, `construit`, `nesigur`), data defrișării și data apariției modulelor, MWp estimat din suprafața panourilor și jurnalul de dovezi (data imaginii, produs, tile).
- **Zone:** TRACK (Dolj, Gorj: Tismana, Rovinari, Ișalnița) și CHECK (Dâmbovița, Giurgiu: Văcărești, Titu).

Structură:

- `notebooks/`: explorare și prototipuri. Curățați output-urile înainte de commit.
- `src/`: cod reutilizabil (preprocesare, compozite, segmentare, clasificarea stadiului).
- `config/`: parametri (zone de interes, intervale de timp, praguri) în YAML/JSON.

Cheile și fișierele de autentificare (Earth Engine, openEO) nu se urcă în repo.
