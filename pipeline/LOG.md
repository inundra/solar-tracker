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
