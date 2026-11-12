# Pipeline Satelitar

**Responsabil:** echipa Pipeline Satelitar

- **Surse:** Sentinel-2 (optic), Sentinel-1 (radar, util când e înnorat).
- **Platforme:** Google Earth Engine și/sau openEO.
- **Mască de nori:** Cloud Score+.
- **Ieșiri:** poligoane de parcuri solare și stadiul construcției pe date.

Structură:

- `notebooks/`: explorare și prototipuri. Curățați output-urile înainte de commit.
- `src/`: cod reutilizabil (preprocesare, compozite, segmentare, clasificarea stadiului).
- `config/`: parametri (zone de interes, intervale de timp, praguri) în YAML/JSON.

Cheile și fișierele de autentificare (Earth Engine, openEO) nu se urcă în repo.
