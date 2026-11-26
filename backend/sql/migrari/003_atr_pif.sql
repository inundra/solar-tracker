-- 003: lista ATR reală (26 noiembrie 2026)
-- Coloana PIF din lista Guvernului e text liber („PIF estimat la 31.12.2027”, „PIF/11.04.2012”, „Finalizat cu PIF”,
-- „Anulat”). Păstrăm textul original și, separat, starea, data și anul interpretate. Unele ATR-uri acoperă
-- mai multe județe („Arad si Timis”): primul rămâne în `judet`, celelalte în `judete_secundare`.

ALTER TABLE atr
    ADD COLUMN pif_text          text,
    ADD COLUMN stare_pif         text CHECK (stare_pif IN ('estimat', 'realizat', 'anulat', 'retehnologizat', 'necunoscut')),
    ADD COLUMN an_pif            smallint CHECK (an_pif BETWEEN 1990 AND 2100),
    ADD COLUMN judete_secundare  text[] NOT NULL DEFAULT '{}',
    ADD COLUMN reparat           boolean NOT NULL DEFAULT false;   -- o celulă a fost corectată la import (vezi note)

-- v_atr a fost creată cu a.*: o refacem ca să includă coloanele noi.
DROP VIEW v_atr;
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
