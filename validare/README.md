# Setul de adevăr și validarea

**Responsabil:** echipa Setul de adevăr și validarea

- `proiecte_cartate/`: 30 de proiecte cartate manual (GeoJSON), fiecare cu stadiul construcției pe date și legătura la ATR.
- `rezultate/`: comparația dintre ieșirile pipeline-ului și setul de adevăr (IoU, precizie, recall, acuratețea stadiului, eroarea la date și eroarea MWp față de valorile raportate de dezvoltatori; ținta este ±8%).

Reguli:

- Evaluarea se face leave-one-park-out: modelul e testat pe un parc pe care nu l-a văzut la antrenare.
- Parcurile CHECK (Văcărești, Titu) au MWp și date cunoscute și servesc la verificarea modelului.

- Setul de adevăr se păstrează separat de datele de antrenare.
- Pentru fiecare proiect notați sursa (imagine, dată) și cine l-a cartat.
