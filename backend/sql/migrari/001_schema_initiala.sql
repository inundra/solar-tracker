-- 001: schema inițială MWitness (issue #13)
-- Parcuri, stadii din setul de adevăr, observații satelitare și stadii prezise de pipeline.
-- Formatul CSV de intrare: validare/schema_csv.md (issue #14). Descrierea tabelelor: backend/schema.md.

CREATE EXTENSION IF NOT EXISTS postgis;

-- Stadiile permise, comune setului de adevăr și pipeline-ului.
-- `ordine` dă succesiunea teren_gol → santier → panouri → gata; `nesigur` nu are ordine.
CREATE TABLE stadii (
    cod            text PRIMARY KEY,
    ordine         smallint UNIQUE,
    stadiu_produs  text NOT NULL,
    descriere      text NOT NULL
);

INSERT INTO stadii (cod, ordine, stadiu_produs, descriere) VALUES
    ('teren_gol', 0, 'neînceput',      'teren agricol, pășune sau teren viran; nicio lucrare'),
    ('santier',   1, 'în construcție', 'teren decopertat sau nivelat, drumuri de șantier, piloni, utilaje; fără panouri'),
    ('panouri',   2, 'în construcție', 'panouri montate pe o parte din suprafață (sub ~90%)'),
    ('gata',      3, 'construit',      'panouri pe toată suprafața, șantier strâns'),
    ('nesigur',   NULL, 'nesigur',     'imaginile nu permit o decizie');

-- Un parc solar. Cheia `parc_id` vine din parcuri.csv și nu se schimbă niciodată.
CREATE TABLE parcuri (
    parc_id          text PRIMARY KEY CHECK (parc_id ~ '^[A-Z]{1,2}-[0-9]{3}$'),
    nume             text NOT NULL,
    judet            text NOT NULL CHECK (judet ~ '^[A-Z]{1,2}$'),
    uat              text,
    geom             geometry(Point, 4326) NOT NULL,       -- centrul parcului (lat/lon din CSV)
    poligon          geometry(MultiPolygon, 4326),         -- gardul parcului, din proiecte_cartate/<parc_id>.geojson
    mwp              numeric(9, 3) CHECK (mwp >= 0),
    mwac             numeric(9, 3) CHECK (mwac >= 0),
    sursa_mw         text,
    detinator        text,
    cui              text CHECK (cui ~ '^[0-9]{2,10}$'),
    atr_numar        text,
    atr_data         date,
    atr_mw           numeric(9, 3) CHECK (atr_mw >= 0),
    rol              text NOT NULL CHECK (rol IN ('track', 'check', 'test', 'lista')),
    stadiu_curent    text NOT NULL REFERENCES stadii (cod),
    data_verificare  date NOT NULL,
    sursa            text NOT NULL,
    verificat_de     text NOT NULL,
    note             text,
    creat_la         timestamptz NOT NULL DEFAULT now(),
    actualizat_la    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sursa_mw_obligatorie CHECK ((mwp IS NULL AND mwac IS NULL) OR sursa_mw IS NOT NULL)
);

CREATE INDEX parcuri_geom_idx    ON parcuri USING gist (geom);
CREATE INDEX parcuri_poligon_idx ON parcuri USING gist (poligon);
CREATE INDEX parcuri_judet_idx   ON parcuri (judet);
CREATE INDEX parcuri_cui_idx     ON parcuri (cui);

-- Stadiul lună de lună stabilit manual de echipa Setul de adevăr (stadii_lunare.csv).
-- `luna` e prima zi a lunii (2025-03 → 2025-03-01).
CREATE TABLE stadii_adevar (
    parc_id        text NOT NULL REFERENCES parcuri (parc_id) ON DELETE CASCADE,
    luna           date NOT NULL CHECK (luna = date_trunc('month', luna)::date),
    stadiu         text NOT NULL REFERENCES stadii (cod),
    sursa_imagine  text CHECK (sursa_imagine IN ('sentinel-2', 'sentinel-1', 'google-earth', 'planet', 'ortofoto', 'alta')),
    data_imagine   date,
    id_imagine     text,
    verificat_de   text NOT NULL,
    note           text,
    actualizat_la  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (parc_id, luna),
    CONSTRAINT imagine_obligatorie CHECK (stadiu = 'nesigur' OR (sursa_imagine IS NOT NULL AND data_imagine IS NOT NULL)),
    CONSTRAINT imagine_in_luna CHECK (data_imagine IS NULL OR date_trunc('month', data_imagine)::date = luna)
);

-- O imagine satelitară analizată de pipeline pentru un parc (o linie pe parc și imagine).
-- `indici` ține valorile calculate (ex. {"ndvi_median": 0.21, "vh_db": -14.2}), ca schema să nu se schimbe la fiecare indice nou.
CREATE TABLE observatii (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parc_id          text NOT NULL REFERENCES parcuri (parc_id) ON DELETE CASCADE,
    data_imagine     date NOT NULL,
    sursa_imagine    text NOT NULL CHECK (sursa_imagine IN ('sentinel-2', 'sentinel-1', 'google-earth', 'planet', 'ortofoto', 'alta')),
    id_imagine       text NOT NULL,                        -- produsul (ex. S2B_MSIL2A_...) sau tile + dată
    cer_senin        numeric(4, 3) CHECK (cer_senin BETWEEN 0 AND 1),   -- Cloud Score+ pe poligonul parcului
    indici           jsonb NOT NULL DEFAULT '{}'::jsonb,
    versiune_pipeline text NOT NULL,
    creat_la         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (parc_id, sursa_imagine, id_imagine, versiune_pipeline)
);

CREATE INDEX observatii_parc_data_idx ON observatii (parc_id, data_imagine);

-- Stadiul prezis de pipeline pe parc și lună. Aceeași cheie ca stadii_adevar, plus versiunea modelului,
-- ca să putem compara mai multe versiuni cu setul de adevăr.
CREATE TABLE stadii_pipeline (
    parc_id              text NOT NULL REFERENCES parcuri (parc_id) ON DELETE CASCADE,
    luna                 date NOT NULL CHECK (luna = date_trunc('month', luna)::date),
    versiune_model       text NOT NULL,
    stadiu               text NOT NULL REFERENCES stadii (cod),
    incredere            numeric(4, 3) CHECK (incredere BETWEEN 0 AND 1),
    mwp_estimat          numeric(9, 3) CHECK (mwp_estimat >= 0),
    mwp_min              numeric(9, 3) CHECK (mwp_min >= 0),
    mwp_max              numeric(9, 3) CHECK (mwp_max >= 0),
    suprafata_panouri_ha numeric(9, 3) CHECK (suprafata_panouri_ha >= 0),
    observatie_id        bigint REFERENCES observatii (id) ON DELETE SET NULL,  -- imaginea decisivă (dovada)
    rulat_la             timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (parc_id, luna, versiune_model),
    CONSTRAINT interval_mwp CHECK (mwp_min IS NULL OR mwp_max IS NULL OR mwp_min <= mwp_max)
);

-- Jurnalul importurilor CSV: ce fișier (hash), când și cu ce rezultat.
CREATE TABLE importuri (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fisier        text NOT NULL,
    sha256        text NOT NULL,
    linii         integer NOT NULL,
    inserate      integer NOT NULL,
    actualizate   integer NOT NULL,
    neschimbate   integer NOT NULL,
    sterse        integer NOT NULL DEFAULT 0,
    importat_la   timestamptz NOT NULL DEFAULT now()
);

-- Parcurile cu lat/lon, suprafața poligonului și stadiul din produs: pentru hartă și API.
CREATE VIEW v_parcuri AS
SELECT p.*,
       ST_Y(p.geom) AS lat,
       ST_X(p.geom) AS lon,
       round((ST_Area(p.poligon::geography) / 10000)::numeric, 2) AS suprafata_ha,
       s.stadiu_produs
FROM parcuri p
JOIN stadii s ON s.cod = p.stadiu_curent;

-- Setul de adevăr față de pipeline, lună de lună: baza metricilor de validare.
CREATE VIEW v_comparatie_stadii AS
SELECT a.parc_id,
       a.luna,
       a.stadiu   AS stadiu_adevar,
       p.versiune_model,
       p.stadiu   AS stadiu_pipeline,
       p.incredere,
       a.stadiu = p.stadiu AS corect
FROM stadii_adevar a
JOIN stadii_pipeline p USING (parc_id, luna);
