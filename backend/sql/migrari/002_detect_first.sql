-- 002: planul „detect-first” (21 noiembrie 2026)
-- Locațiile ATR-urilor nu sunt publice (lista Guvernului dă doar județul), deci pornim de la ce detectează
-- satelitul și legăm detecțiile de ATR-uri după județ, MW și titular. Harta națională compară, pe județ,
-- MW aprobați (ATR) cu MW construiți (detecții). Descriere: backend/schema.md.

-- Parametri folosiți în vederi; se schimbă cu UPDATE, fără migrare nouă.
CREATE TABLE parametri (
    cheie      text PRIMARY KEY,
    valoare    numeric NOT NULL,
    descriere  text NOT NULL
);

INSERT INTO parametri (cheie, valoare, descriere) VALUES
    ('mwp_pe_ha',     0.70, 'MWp estimați pe hectar de parc (gard), când pipeline-ul nu dă MWp'),
    ('mwp_pe_ha_min', 0.50, 'capătul de jos al intervalului MWp/ha'),
    ('mwp_pe_ha_max', 0.90, 'capătul de sus al intervalului MWp/ha'),
    ('dc_ac',         1.20, 'raportul tipic MWp (DC) / MW din ATR (AC), folosit la legarea de ATR-uri');

CREATE FUNCTION parametru(p_cheie text) RETURNS numeric
    LANGUAGE sql STABLE AS $$ SELECT valoare FROM parametri WHERE cheie = p_cheie $$;

-- Județele: codul auto (ca în parcuri.csv), numele și reședința. `centru` e reședința (pentru hartă când
-- lipsește conturul); `contur` se încarcă opțional dintr-un GeoJSON cu `importa_judete.py`.
CREATE TABLE judete (
    cod        text PRIMARY KEY CHECK (cod ~ '^[A-Z]{1,2}$'),
    nume       text NOT NULL UNIQUE,
    resedinta  text NOT NULL,
    centru     geometry(Point, 4326) NOT NULL,
    contur     geometry(MultiPolygon, 4326)
);

CREATE INDEX judete_contur_idx ON judete USING gist (contur);

INSERT INTO judete (cod, nume, resedinta, centru)
SELECT cod, nume, resedinta, ST_SetSRID(ST_MakePoint(lon, lat), 4326)
FROM (VALUES
    ('AB', 'Alba', 'Alba Iulia', 46.067, 23.570),
    ('AR', 'Arad', 'Arad', 46.176, 21.319),
    ('AG', 'Argeș', 'Pitești', 44.856, 24.869),
    ('BC', 'Bacău', 'Bacău', 46.567, 26.914),
    ('BH', 'Bihor', 'Oradea', 47.072, 21.921),
    ('BN', 'Bistrița-Năsăud', 'Bistrița', 47.133, 24.500),
    ('BT', 'Botoșani', 'Botoșani', 47.748, 26.669),
    ('BV', 'Brașov', 'Brașov', 45.657, 25.601),
    ('BR', 'Brăila', 'Brăila', 45.271, 27.957),
    ('B',  'București', 'București', 44.433, 26.104),
    ('BZ', 'Buzău', 'Buzău', 45.150, 26.823),
    ('CS', 'Caraș-Severin', 'Reșița', 45.301, 21.889),
    ('CL', 'Călărași', 'Călărași', 44.200, 27.331),
    ('CJ', 'Cluj', 'Cluj-Napoca', 46.770, 23.590),
    ('CT', 'Constanța', 'Constanța', 44.173, 28.638),
    ('CV', 'Covasna', 'Sfântu Gheorghe', 45.864, 25.788),
    ('DB', 'Dâmbovița', 'Târgoviște', 44.925, 25.457),
    ('DJ', 'Dolj', 'Craiova', 44.319, 23.800),
    ('GL', 'Galați', 'Galați', 45.435, 28.008),
    ('GR', 'Giurgiu', 'Giurgiu', 43.904, 25.969),
    ('GJ', 'Gorj', 'Târgu Jiu', 45.035, 23.275),
    ('HR', 'Harghita', 'Miercurea Ciuc', 46.358, 25.802),
    ('HD', 'Hunedoara', 'Deva', 45.883, 22.901),
    ('IL', 'Ialomița', 'Slobozia', 44.564, 27.363),
    ('IS', 'Iași', 'Iași', 47.159, 27.587),
    ('IF', 'Ilfov', 'Buftea', 44.561, 25.949),
    ('MM', 'Maramureș', 'Baia Mare', 47.657, 23.568),
    ('MH', 'Mehedinți', 'Drobeta-Turnu Severin', 44.631, 22.656),
    ('MS', 'Mureș', 'Târgu Mureș', 46.542, 24.557),
    ('NT', 'Neamț', 'Piatra Neamț', 46.927, 26.371),
    ('OT', 'Olt', 'Slatina', 44.430, 24.371),
    ('PH', 'Prahova', 'Ploiești', 44.946, 26.036),
    ('SM', 'Satu Mare', 'Satu Mare', 47.792, 22.886),
    ('SJ', 'Sălaj', 'Zalău', 47.193, 23.057),
    ('SB', 'Sibiu', 'Sibiu', 45.793, 24.152),
    ('SV', 'Suceava', 'Suceava', 47.651, 26.255),
    ('TR', 'Teleorman', 'Alexandria', 43.969, 25.333),
    ('TM', 'Timiș', 'Timișoara', 45.754, 21.226),
    ('TL', 'Tulcea', 'Tulcea', 45.179, 28.805),
    ('VS', 'Vaslui', 'Vaslui', 46.640, 27.729),
    ('VL', 'Vâlcea', 'Râmnicu Vâlcea', 45.100, 24.369),
    ('VN', 'Vrancea', 'Focșani', 45.697, 27.186)
) AS j (cod, nume, resedinta, lat, lon);

ALTER TABLE parcuri ADD CONSTRAINT parcuri_judet_fk FOREIGN KEY (judet) REFERENCES judete (cod);

-- Companiile titulare de ATR, după CUI.
CREATE TABLE companii (
    cui            text PRIMARY KEY CHECK (cui ~ '^[0-9]{2,10}$'),
    nume           text NOT NULL,
    actualizat_la  timestamptz NOT NULL DEFAULT now()
);

-- Un aviz tehnic de racordare, cum apare în lista Guvernului (date Transelectrica) sau în altă sursă.
-- Locația e doar județul; `localitate` se completează manual (APM, primării) pentru proiectele legate.
CREATE TABLE atr (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numar          text NOT NULL,
    data_atr       date,
    titular        text NOT NULL,
    cui            text REFERENCES companii (cui),
    judet          text NOT NULL REFERENCES judete (cod),
    mw             numeric(9, 3) NOT NULL CHECK (mw >= 0),
    operator       text,                  -- Transelectrica sau distribuitorul
    etapa          text,                  -- etapa din listă (ex. „contract de racordare”)
    data_pif       date,                  -- data estimată de punere în funcțiune
    tehnologie     text NOT NULL DEFAULT 'necunoscuta'
                   CHECK (tehnologie IN ('fotovoltaic', 'stocare', 'hibrid', 'eolian', 'alta', 'necunoscuta')),
    localitate     text,
    sursa          text NOT NULL,
    note           text,
    creat_la       timestamptz NOT NULL DEFAULT now(),
    actualizat_la  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (numar, titular, judet)
);

CREATE INDEX atr_judet_idx ON atr (judet);
CREATE INDEX atr_cui_idx   ON atr (cui);

-- Un parc sau șantier găsit pe imagini: de pipeline (detecție de schimbare), dintr-un set deschis
-- (TZ-SAM, OpenStreetMap) sau desenat manual. Nu știm de la început cărui ATR îi aparține.
CREATE TABLE detectii (
    detectie_id        text PRIMARY KEY CHECK (detectie_id ~ '^[A-Za-z0-9_.:-]{1,64}$'),
    sursa              text NOT NULL CHECK (sursa IN ('pipeline', 'tz-sam', 'osm', 'manual')),
    judet              text NOT NULL REFERENCES judete (cod),
    uat                text,
    poligon            geometry(MultiPolygon, 4326) NOT NULL,
    tip                text NOT NULL DEFAULT 'fotovoltaic' CHECK (tip IN ('fotovoltaic', 'stocare', 'necunoscut')),
    stadiu_curent      text NOT NULL REFERENCES stadii (cod),
    data_stadiu        date,              -- data imaginii pe care s-a stabilit stadiul curent
    data_defrisare     date,              -- prima imagine cu teren decopertat
    data_module        date,              -- prima imagine cu panouri
    incredere          numeric(4, 3) CHECK (incredere BETWEEN 0 AND 1),
    mwp_estimat        numeric(9, 3) CHECK (mwp_estimat >= 0),
    mwp_min            numeric(9, 3) CHECK (mwp_min >= 0),
    mwp_max            numeric(9, 3) CHECK (mwp_max >= 0),
    parc_id            text REFERENCES parcuri (parc_id) ON DELETE SET NULL,  -- dacă e un parc din setul de adevăr
    duplicat_al        text REFERENCES detectii (detectie_id) ON DELETE SET NULL,
    versiune_pipeline  text,
    prima_detectare    timestamptz NOT NULL DEFAULT now(),
    actualizat_la      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT interval_mwp CHECK (mwp_min IS NULL OR mwp_max IS NULL OR mwp_min <= mwp_max),
    CONSTRAINT ordine_date CHECK (data_defrisare IS NULL OR data_module IS NULL OR data_defrisare <= data_module),
    CONSTRAINT nu_e_duplicat_al_lui CHECK (duplicat_al IS DISTINCT FROM detectie_id)
);

CREATE INDEX detectii_poligon_idx ON detectii USING gist (poligon);
CREATE INDEX detectii_judet_idx   ON detectii (judet);

-- Jurnalul dovezilor: fiecare imagine pe care s-a văzut un stadiu, cu produsul și tile-ul,
-- ca raportul să poată arăta exact pe ce se bazează.
CREATE TABLE jurnal_detectii (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    detectie_id        text NOT NULL REFERENCES detectii (detectie_id) ON DELETE CASCADE,
    data_imagine       date NOT NULL,
    stadiu             text NOT NULL REFERENCES stadii (cod),
    sursa_imagine      text NOT NULL CHECK (sursa_imagine IN ('sentinel-2', 'sentinel-1', 'google-earth', 'planet', 'ortofoto', 'alta')),
    id_imagine         text NOT NULL,
    tile               text,
    cer_senin          numeric(4, 3) CHECK (cer_senin BETWEEN 0 AND 1),
    suprafata_ha       numeric(9, 3) CHECK (suprafata_ha >= 0),
    versiune_pipeline  text NOT NULL DEFAULT '',
    note               text,
    creat_la           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (detectie_id, sursa_imagine, id_imagine, versiune_pipeline)
);

CREATE INDEX jurnal_detectii_data_idx ON jurnal_detectii (detectie_id, data_imagine);

-- Legătura detecție ↔ ATR. `leaga_atr.py` propune candidați (stare `propusa`, cu scor și motive);
-- un om îi confirmă sau îi respinge. O detecție are cel mult un ATR confirmat.
CREATE TABLE legaturi_atr (
    detectie_id  text NOT NULL REFERENCES detectii (detectie_id) ON DELETE CASCADE,
    atr_id       bigint NOT NULL REFERENCES atr (id) ON DELETE CASCADE,
    scor         numeric(4, 3) NOT NULL CHECK (scor BETWEEN 0 AND 1),
    motive       jsonb NOT NULL DEFAULT '{}'::jsonb,
    stare        text NOT NULL DEFAULT 'propusa' CHECK (stare IN ('propusa', 'confirmata', 'respinsa')),
    decis_de     text,
    decis_la     timestamptz,
    note         text,
    creat_la     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (detectie_id, atr_id),
    CONSTRAINT decizie_semnata CHECK (stare = 'propusa' OR decis_de IS NOT NULL)
);

CREATE UNIQUE INDEX legaturi_atr_o_confirmare ON legaturi_atr (detectie_id) WHERE stare = 'confirmata';
CREATE INDEX legaturi_atr_atr_idx ON legaturi_atr (atr_id);

-- Detecțiile cu centru, suprafață, MWp (din pipeline sau estimat din suprafață) și ATR-ul confirmat.
CREATE VIEW v_detectii AS
WITH d AS (
    SELECT d.*,
           ST_PointOnSurface(d.poligon) AS centru,
           (ST_Area(d.poligon::geography) / 10000)::numeric AS ha
    FROM detectii d
)
SELECT d.detectie_id, d.sursa, d.judet, d.uat, d.poligon, d.tip, d.stadiu_curent, s.stadiu_produs,
       d.data_stadiu, d.data_defrisare, d.data_module, d.incredere,
       ST_Y(d.centru) AS lat,
       ST_X(d.centru) AS lon,
       round(d.ha, 2) AS suprafata_ha,
       round(coalesce(d.mwp_estimat, d.ha * parametru('mwp_pe_ha')), 2)     AS mwp,
       round(coalesce(d.mwp_min, d.ha * parametru('mwp_pe_ha_min')), 2)     AS mwp_min,
       round(coalesce(d.mwp_max, d.ha * parametru('mwp_pe_ha_max')), 2)     AS mwp_max,
       d.mwp_estimat IS NULL AS mwp_din_suprafata,
       d.parc_id, d.duplicat_al, d.versiune_pipeline, d.prima_detectare, d.actualizat_la,
       l.atr_id, a.numar AS atr_numar, a.titular AS atr_titular, a.cui AS atr_cui, a.mw AS atr_mw
FROM d
JOIN stadii s ON s.cod = d.stadiu_curent
LEFT JOIN legaturi_atr l ON l.detectie_id = d.detectie_id AND l.stare = 'confirmata'
LEFT JOIN atr a ON a.id = l.atr_id;

-- Fiecare ATR cu ce s-a găsit pe teren: detecția confirmată (dacă există) și stadiul ei.
-- `stare_teren` = 'fara_santier_legat' înseamnă că n-am legat nicio detecție de el (încă).
CREATE VIEW v_atr AS
SELECT a.*,
       j.nume AS judet_nume,
       l.detectie_id,
       d.stadiu_curent AS stadiu_detectie,
       d.stadiu_produs,
       d.mwp AS mwp_detectat,
       d.data_defrisare,
       d.data_module,
       CASE WHEN l.detectie_id IS NULL THEN 'fara_santier_legat' ELSE d.stadiu_curent END AS stare_teren,
       (SELECT count(*) FROM legaturi_atr p WHERE p.atr_id = a.id AND p.stare = 'propusa') AS candidati
FROM atr a
JOIN judete j ON j.cod = a.judet
LEFT JOIN legaturi_atr l ON l.atr_id = a.id AND l.stare = 'confirmata'
LEFT JOIN v_detectii d ON d.detectie_id = l.detectie_id;

-- Harta națională: pe fiecare județ, MW aprobați în ATR-uri față de MWp detectați pe teren.
-- Duplicatele (același parc din două surse) nu se numără de două ori.
CREATE VIEW v_judete AS
WITH a AS (
    SELECT judet,
           count(*)                                              AS nr_atr,
           sum(mw)                                               AS mw_aprobat,
           sum(mw) FILTER (WHERE tehnologie IN ('fotovoltaic', 'hibrid'))  AS mw_aprobat_fotovoltaic,
           sum(mw) FILTER (WHERE tehnologie = 'stocare')         AS mw_aprobat_stocare
    FROM atr GROUP BY judet
), d AS (
    SELECT judet,
           count(*)                                                        AS nr_detectii,
           sum(mwp) FILTER (WHERE stadiu_curent = 'gata')                  AS mwp_construit,
           sum(mwp) FILTER (WHERE stadiu_curent IN ('santier', 'panouri')) AS mwp_in_constructie,
           count(*) FILTER (WHERE stadiu_curent IN ('santier', 'panouri')) AS nr_santiere,
           count(*) FILTER (WHERE atr_id IS NOT NULL)                      AS nr_legate_de_atr
    FROM v_detectii WHERE duplicat_al IS NULL GROUP BY judet
)
SELECT j.cod AS judet, j.nume, j.resedinta,
       ST_Y(j.centru) AS lat, ST_X(j.centru) AS lon, j.contur,
       coalesce(a.nr_atr, 0)                   AS nr_atr,
       coalesce(a.mw_aprobat, 0)               AS mw_aprobat,
       coalesce(a.mw_aprobat_fotovoltaic, 0)   AS mw_aprobat_fotovoltaic,
       coalesce(a.mw_aprobat_stocare, 0)       AS mw_aprobat_stocare,
       coalesce(d.nr_detectii, 0)              AS nr_detectii,
       coalesce(round(d.mwp_construit, 1), 0)       AS mwp_construit,
       coalesce(round(d.mwp_in_constructie, 1), 0)  AS mwp_in_constructie,
       coalesce(d.nr_santiere, 0)              AS nr_santiere,
       coalesce(d.nr_legate_de_atr, 0)         AS nr_legate_de_atr,
       CASE WHEN coalesce(a.mw_aprobat, 0) > 0
            THEN round(100 * (coalesce(d.mwp_construit, 0) + coalesce(d.mwp_in_constructie, 0))
                       / parametru('dc_ac') / a.mw_aprobat, 1)
       END AS procent_vizibil_pe_teren   -- (construit + în construcție, convertit în AC) / aprobat
FROM judete j
LEFT JOIN a ON a.judet = j.cod
LEFT JOIN d ON d.judet = j.cod;
