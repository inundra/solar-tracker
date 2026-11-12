# Date / Backend

**Responsabil:** echipa Date / Backend

Baza de date PostgreSQL + PostGIS cu:

- **ATR-uri** (avize tehnice de racordare): putere, nod de racordare, dată, stadiu.
- **Companii**: denumire, CUI.
- **Amplasamente**: geometrie (poligon / punct), UAT, județ.
- **CfD și tranzacții**: rezultatele licitațiilor CfD și tranzacțiile cunoscute (vânzări de proiecte, finanțări).
- **Legături** între ATR, companie și amplasament.

Structură:

- `sql/migrari/`: scripturi SQL numerotate (`001_schema_initiala.sql`, `002_...`), rulate în ordine.
- `src/`: cod Python pentru import și curățare (ex.: parsarea listelor de ATR-uri).
- `date_brute/`: doar fișiere mici de exemplu; datele mari nu intră în repo.

Conexiunea la baza de date se configurează prin variabile de mediu (`.env`, care nu se urcă în repo).
