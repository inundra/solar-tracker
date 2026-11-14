# Pipeline work log

Append-only, newest entry **at the top**. One entry per task / check-run / notable finding. Never rewrite old entries; if one was wrong, add a new entry that corrects it.

Template:

```
## YYYY-MM-DD · P<id> · <short title>
- **Done:** what changed (files, params), in 1–3 bullets
- **Why:** the reason or evidence behind the choice
- **Result:** numbers from the run (park, scenes, clear obs, dates, MWp, metrics), or "no run"
- **Not checked / risks:** what's unverified
- **Next:** the next step or the blocker
- **Commit:** <branch> (git log on the branch shows the hash)
```

---

## 2026-11-14 · P4 · Extraction for all 6 parks, orbit fixed, S1 min cover
- **Done:** `src/extract.py`: per site, S2 rows and S1 rows merged server-side, **one `getInfo`** → `data/timeseries/<site>.csv` (column `sensor`; S2 per scene, S1 per date) + `<site>.meta.json` (date range, collections, `s1_orbit`, params hash, extraction time, for `provenance`). Cached; `--refresh` re-extracts; warns when the cache's params hash differs. CLI `python -m src.extract --site X | --all`. Human decisions applied: `s1_orbit` fixed per site in `config/sites.yaml`; new param `s1.min_cover_frac: 0.95` (a partial pass gets `obs=False`, no log-ratio, and stays out of the baseline); `clear_threshold` stays 0.60. `s1.orbit_counts` now counts **distinct dates**, not slices. Fixture `tests/fixtures/tismana_1_sample.csv` (Tismana 1, Aug–Oct 2026, 55 S2 + 15 S1 rows, 14 KB). Tests: 5 new offline.
- **Why:** P4 "done when". The scene-count pick was wrong at Văcărești: orbit 109 had 335 "scenes" against ~200 for the others because the AOI straddles a slice boundary (most dates counted twice). Counting distinct dates fixes it. The orbit is stored per site so the radar series can't switch orbit with the date range (Tismana 1 had a real 34/34 tie over May–Oct).
- **Result:** range 2022-01-01 → 2026-11-13 (last image; meta stores the exclusive end 2026-11-15). Cache now also warns if `s1_orbit` or the start date differ from the cached run; `orbit` / `n_slices` load as Int64. Orbits (distinct dates): Gorj + Dolj → 7 (200 vs 199/198/198), Dâmbovița → 131 (202 vs 200/200/198). Per site, S2 scenes / clear obs | S1 dates (all obs, min cover 1.000): tismana_1 813 / 431 | 200; tismana_2 813 / 431 | 200; rovinari 813 / 421 | 200; isalnita 409 / 213 | 200 (one S2 tile and orbit only, 34TGQ); vacaresti 818 / 374 | 202; titu 816 / 416 | 202. Tismana 1 and 2 share the scene list (same tile) but their values differ (NDVI corr 0.935, mean diff 0.049). 2–4 S2 scenes per site have no Cloud Score+ (`csp_frac = 0`). S1 split-slice dates: tismana_2 15, rovinari 6, others ≤ 1. ~20 s per site. Run logs: `data/logs/tismana_1_20261114-025136.log` (first extraction), then `--all`: `tismana_1_20261114-025210.log` (cache hit), `tismana_2_20261114-025210.log`, `rovinari_20261114-025241.log`, `isalnita_20261114-025256.log`, `vacaresti_20261114-025317.log`, `titu_20261114-025337.log`. Tests: 21 offline + 3 `ee` passed.
- **Not checked / risks:** S1 overlap pixels double-counted on split-slice dates (`shortcut:` in `s1.py`). The orbit pick is nearly a tie everywhere (±2 dates), so it's reproducible but not "better". `min_cover_frac` and the orbit choice change reported numbers → decision-note draft given to the human for `docs/decizii/`. Cache CSVs ~190 KB per site live in `data/` (gitignored).
- **Next:** P5: labels are human-drawn; the agent prepares the labelling notebook.
- **Commit:** pipeline/agent-workflow

## 2026-11-14 · P3 · Sentinel-1 VV/VH series, one orbit
- **Done:** `src/s1.py`: `COPERNICUS/S1_GRD`, IW, VV+VH, one relative orbit. `pick_orbit()` (pure): the orbit with the most scenes in the range, ties to the lowest number. Per scene, server-side: dB → linear power, `focalMedian(speckle_radius_m)`, linear sum + pixel count over the AOI on the scene's native grid, `cover_frac`. `to_frame()` (pure): merges same-date slices pixel-weighted, converts to dB, `*_lr` = dB vs the mean linear power of the previous `baseline_days` (window [t-90 d, t); empty → NaN). CLI `python -m src.s1`. `to_frame` refuses rows from more than one orbit. Tests: 5 offline + 1 `ee`.
- **Why:** P3 "done when". Averaging in linear power, not dB, keeps means and ratios physically right. Slice merging covers an AOI split by a slice boundary. Picking the orbit by most scenes plus a fixed tie-break makes the choice reproducible and keeps it out of params.
- **Result:** Tismana 1, 2026-05-01 → 2026-11-01: orbits {7: 34, 29: 34, 80: 32, 102: 33}, chose 7 (DESCENDING, S1A/C/D). 34 dates, all `cover_frac` 1.000, no split slices. VV -11.1 to -15.1 dB, VH -17.9 to -22.3 dB; slow decline Aug–Oct (lr ≈ -1 to -1.4 dB). **Single-date spikes above `decisive_db` = 1.5: +2.34 dB VV on 2026-05-12 and +2.46 dB on 2026-10-22; 10-28 back to 0.05.** Pattern fits wet soil after rain, not construction. Run log: `data/logs/tismana_1_20261114-023915.log`. Tests: 14 offline + 3 `ee` passed.
- **Not checked / risks:** spike cause not verified against weather data. The tie between orbits 7 and 29 means a different range can pick a different orbit; P4 must pick once over the full range and store it. The baseline is a trailing mean, so a lasting change shows as lr ≠ 0 only until the baseline catches up (about 90 days); stage logic must read it as a step, not a level. S1 visual check not done (not required). Reviewer advisories left open: no minimum `cover_frac` for an S1 observation (needs a new param `s1.min_cover_frac` → human decision before P7); orbit counts are per slice, not per covered date (no effect while cover = 1.000).
- **Next:** P4 (`extract.py`: all 6 parks, 2022-01-01 → today, cached CSV).
- **Commit:** pipeline/agent-workflow

## 2026-11-14 · P2 · Sentinel-2 + Cloud Score+ per-scene rows
- **Done:** `src/s2.py`: S2 SR harmonized linked to Cloud Score+ `cs_cdf`; per scene, server-side `reduceRegion(scale=10, maxPixels=1e9)`: `clear_frac` (share of AOI with `cs_cdf ≥ clear_threshold`, masked / off-footprint = not clear), mean NDVI / NDBI / BSI over clear pixels; `csp_frac` (AOI share with a Cloud Score+ value, separates missing CS+ from overcast); reductions on the scene's UTM grid (`crs` = B4 projection); date, `system:index`, `PRODUCT_ID`, `MGRS_TILE`. `to_frame()` (pure) flags `obs = clear_frac ≥ min_clear_frac`. `thumb_urls()` for spot-checks; CLI `python -m src.s2`. `src/params.py` (load + hash) used by `run.py` too. Notebook `notebooks/p2_s2_spotcheck.ipynb` (outputs stripped).
- **Why:** P2 "done when". Counting no-data as not clear keeps a scene that only half-covers the AOI from looking clear. Indices only over clear pixels so cloud doesn't leak into them.
- **Result:** Tismana 1, 2026-08-01 → 2026-11-01: 55 scenes (tile 34TFQ, orbits R093 + R136, S2A/B/C), 40 clear obs at 0.80, one `getInfo`. NDVI ~0.43 → ~0.30 and BSI 0.03 → 0.17 over the period (levelling continues). Spot-check (thumbnails viewed): 2026-09-07 clear 1.000, mask right; 2026-10-02 clear 0.421, haze in E half masked correctly; **2026-10-17 clear 0.916 but thin haze over the whole scene, NDVI 0.21 vs ~0.37 neighbours: haze passes `cs_cdf ≥ 0.60`.** After reviewer fixes (UTM `crs`, `csp_frac`): unchanged 55 / 40, `no_cloudscore=0`, so the 7 scenes at clear 0.000 are real overcast. Also viewed 2026-10-07 (clear 1.000, NDVI 0.290: looks clear; farmland in the AOI's N part browned/ploughed since Sept) and 2026-10-09 (clear 1.000, NDVI 0.244: light haze, like 10-17). Run log: `data/logs/tismana_1_20261114-023048.log`. Tests: 10 offline + 2 `ee` passed.
- **Not checked / risks:** haze leak above, left as is (changing `clear_threshold` changes results → human decision; `confirm_n = 2` in P7 should absorb single dips). The AOI buffer includes farmland whose seasonal change moves NDVI without construction; class fractions (P6) restricted to the AOI should matter more than whole-AOI index means. Same-day duplicates exist (two satellites / orbits on one date, e.g. 2026-08-05); P4/P7 must decide whether to merge them. Only one park checked; other tiles not seen yet.
- **Next:** P3 (S1 VV/VH, single relative orbit).
- **Commit:** pipeline/agent-workflow

## 2026-11-14 · cleanup · Reviewer advisories and doc drift
- **Done:** leakage test also flags `proiecte_cartate` (the GT subfolder), not only `validare`; `CLAUDE.md` `sites.py` line now says geometry stays raw and `aoi()` builds the `ee.Geometry`. Desktop kit re-synced; its README marks install steps 1–3 done.
- **Why:** P0/P1 reviewer advisories that need no teammate input. CLAUDE.md described an API the code doesn't have.
- **Result:** `pytest -q` 7 passed; a planted `proiecte_cartate/x` string in `src/` fails the leakage test as intended. No pipeline run.
- **Not checked / risks:** `.claude/settings.json` still only allows `python -m pytest` / `python -m src.run`, not the `..\.venv` interpreter EE needs, so venv commands prompt; adding them was blocked by the permission classifier and is left to the human.
- **Next:** P2.
- **Commit:** pipeline/agent-workflow

## 2026-11-14 · P1 · EE client and site loader
- **Done:** `src/ee_client.py` (`init()`: project from `EE_PROJECT`, clear errors for unset / not authenticated); `src/sites.py` (`load`, `get`, `aoi` → `ee.Geometry.Polygon`, `area_ha`). `run.py --dry` now validates `--site` against `sites.yaml` before logging, initialises EE, logs project and AOI area, stops before extraction. Tests: `tests/test_sites.py` (4 offline + 1 `ee`); `test_log.py` stubs EE.
- **Why:** P1 "done when". Validating the id first stops `--site ../x` from writing logs outside `data/logs/` (P0 reviewer advisory). Geometry stays raw in `sites.py` so loading is testable offline.
- **Result:** `pytest -q` 7 passed; `pytest -m ee` 1 passed. Dry run AOI areas (ha): tismana_1 434.0, tismana_2 265.4, rovinari 216.1, isalnita 328.5, vacaresti 311.6, titu 155.6; same as the setup entries. Run log: `data/logs/tismana_1_20261114-020947.log`. `EE_PROJECT` unset → "EE_PROJECT is not set: run `setx EE_PROJECT ...`"; unknown site → argparse error listing valid ids.
- **Not checked / risks:** earthengine-api lives only in the repo-root `.venv` (system Python lacks it); run with `..\.venv\Scripts\python.exe`. Auth-failure message not tested live (would need revoking credentials).
- **Next:** P2 (S2 + Cloud Score+, per-scene clear_frac).
- **Commit:** pipeline/agent-workflow

## 2026-11-14 · docs · Pipeline README now English, merged with kit README
- **Done:** replaced the Romanian `README.md` with the kit's English README, adapted for the repo (layout, setup, run, agent use, records, workflow), and carried over the Romanian facts (owner, sources, platform, cloud mask, outputs, study areas, structure, no keys in git). `CLAUDE.md` language rule and P15 updated to match. `check-run` skill now fits on the other 5 parks (commit 0ce58bd).
- **Why:** human decision: one README in the pipeline folder; the kit README lived only on the desktop, so teammates never saw how to use the agent.
- **Result:** no run.
- **Not checked / risks:** the team README changed language; the other pipeline team members haven't seen it yet. Giurgiu CHECK park still open (APPROACH § 5).
- **Next:** P1.
- **Commit:** pipeline/agent-workflow

## 2026-11-14 · P0 · Scaffold, leakage test, logging helper
- **Done:** `src/` package with `log.py` (`setup_logging(site)`: console INFO + `data/logs/<site>_<ts>.log` DEBUG, utf-8) and a minimal `run.py` (`--site`, `--dry`, `--refresh`; logs the params hash). Added `tests/` (`test_no_leakage.py`, `test_log.py`), `pytest.ini` (marker `ee`, deselected by default), and `pipeline/.gitignore` (`data/`, `outputs/`). Reworded the comment in `config/sites*.yaml` that named the ground-truth folder.
- **Why:** P0 is the base every later task uses. The leakage test enforces hard rule 1, and it scans raw text, so the warning comment in the config files would have tripped it. Rewording the comment keeps the test strict.
- **Result:** `pytest -q` gives 3 passed. A planted `../validare/` string in `src/` makes the leakage test fail, as it should. `python -m src.run --site tismana_1 --dry` wrote `data/logs/tismana_1_20261114-013228.log` (params_hash=6ca723b715a6). No EE call.
- **Not checked / risks:** branched from `pipeline/agent-workflow`, not `main`, because the kit is not merged yet. The PR must go after (or on top of) that branch. The `ee` marker is deselected by default via `addopts`, so run EE tests with `pytest -m ee`. Python 3.14 + pytest 9.2 on this machine.
- **Next:** P1 (`ee_client.py`, `sites.py`, `--dry` prints AOI area).
- **Commit:** pipeline/p0-scaffold

## 2026-11-14 · setup · Titu AOI corrected
- **Done:** `titu` geometry moved from the block at ~25.59E 44.627N to the site at ~25.617E 44.611N (AOI 156 ha). Corrects the "EE auth + first AOIs" entry.
- **Why:** S2 sequence 2024 → spring 2025 → autumn 2025 → spring 2026: the SE site was cropland in 2024, cleared spring 2025, panels by spring 2026 — matches Enery (construction Feb 2025, energised Mar 2026); one coherent ~60 ha array fits 54 MWp on single-axis trackers; inside Titu UAT, toward Potlogi (Enery's community area). The old pick is an older 2024 park plus 2025–26 extensions (~30 ha new), more consistent with Enexus "Titu 1" (20 MWp). A third new block at ~25.49E 44.62N is in Costeștii din Vale, not Titu.
- **Result:** no run.
- **Not checked / risks:** no official coordinates for Enery Titu; identification is by timing, size and admin area. PV-roofed farm buildings at the E edge sit partly inside the AOI and could add false panel pixels.
- **Next:** P0.
- **Commit:** none yet

## 2026-11-14 · setup · AOIs for Tismana 1, Tismana 2, Rovinari
- **Done:** geometry added for `tismana_1`, `tismana_2`, `rovinari` in `config/sites.yaml`; all 6 sites now have an AOI.
- **Why:** official project points from parc-verde.ro (Tismana 1: 23.09E 44.94N; Tismana 2: 23.12E 44.93N; Rovinari Est: inner dump NE of Rovinari, ~4.5 km from the power plant) matched large NDVI-loss areas (S2, summer 2024 vs Aug–Nov 2026) on the inner dumps. Polygons drawn around the cleared ground + ~200 m.
- **Result:** AOI areas: Tismana 1 434 ha, Tismana 2 265 ha, Rovinari 216 ha. Reported capacity (not in sites.yaml, TRACK parks): 128.3 / 132 / 110 MW.
- **Not checked / risks:** sites are being levelled, no panels yet (commissioning planned 2027), so the final panel footprint may differ from the cleared area; Tismana 1 AOI is ~2.5× the ~160 ha reported park. Edges from 10 m S2, not a hi-res basemap.
- **Next:** human glance on a hi-res basemap; confirm Titu block; then P0.
- **Commit:** none yet

## 2026-11-14 · setup · EE auth + first AOIs in sites.yaml
- **Done:** EE authenticated on project `pro-plasma-514622-n5` (noncommercial, Community). `config/sites.yaml` created; AOIs drawn for Văcărești, Titu, Ișalnița. Tismana split into `tismana_1` / `tismana_2` (6 sites); docs updated from "5 parks".
- **Why:** AOIs located by comparing S2 summer 2024 vs 2026 composites (new PV blocks) + news for project identity; OSM has none of these parks yet. Tismana 1 and 2 are separate project companies.
- **Result:** AOI areas (with buffer): Ișalnița 328 ha, Văcărești 312 ha, Titu 190 ha. Reported MWp: Văcărești 126, Titu 54.28 (sources in sites.yaml).
- **Not checked / risks:** edges drawn on 10 m S2, not a hi-res basemap. Titu: two smaller new blocks nearby (one likely Enexus "Titu 1" 20 MWp) — chosen block unconfirmed. Tismana 1/2 and Rovinari not visible as PV in 2026 S2; location unknown. EE login works only without the Drive scope.
- **Next:** human confirms Titu block and pins Tismana 1, Tismana 2, Rovinari; then P0.
- **Commit:** none yet

## 2026-11-14 · setup · Agent kit added
- **Done:** added CLAUDE.md, BACKLOG.md, CONTRACT.md, APPROACH.md, LOG.md, config templates, reviewer subagent, `/pipeline-task` and `/check-run` skills.
- **Why:** `pipeline/` was empty; the agent needs fixed rules (no GT leakage, leave-one-park-out, no data in git) and a plan to the 11 Dec deadline.
- **Result:** no run.
- **Not checked / risks:** Earth Engine not authenticated yet; dataset IDs and permission syntax not verified live.
- **Next:** EE setup, draw AOIs, then P0.
- **Commit:** none yet
