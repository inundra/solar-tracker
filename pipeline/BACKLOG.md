# Pipeline backlog

Status: `todo` / `doing` / `done` / `blocked(<reason>)`. Do items in order unless told otherwise; each one ends with the Definition of done in `CLAUDE.md`.

## Week 2 (14–20 Nov): data path and filtering

| ID | Status | Task | Done when |
|---|---|---|---|
| P0 | done | Scaffold: `src/` package, `tests/`, `pytest.ini` (marker `ee`), `pipeline/.gitignore` with `data/` and `outputs/`, `tests/test_no_leakage.py` (fails if any file under `src/`, `labels/`, `config/` mentions `validare`), `src/log.py` (one `setup_logging(site)` helper: console INFO + `data/logs/` DEBUG file) | `pytest -q` green with the leakage test; a dry run writes a log file (done: scaffold, leakage test, `src/log.py`, `run --dry` writes log) |
| P1 | todo | `ee_client.py` + `sites.py`; `config/sites.yaml` from the example (geometry drawn by human) | `python -m src.run --site tismana_1 --dry` prints AOI area in ha; clear error when `EE_PROJECT` missing |
| P2 | todo | `s2.py`: S2 SR harmonized + Cloud Score+ (`cs_cdf ≥ 0.60`), per-scene `clear_frac`, indices (NDVI, NDBI, BSI) | For one park and 3 months: table of scenes with clear_frac; spot-check 2 scenes visually in a notebook |
| P3 | todo | `s1.py`: GRD IW VV/VH, single relative orbit, focal-median speckle filter, log-ratio vs baseline window | Same park: VV/VH series per date, orbit recorded |
| P4 | todo | `extract.py`: one server-side FeatureCollection → `data/timeseries/<site>.csv`; cached, `--refresh` to redo | All 6 parks extracted 2022-01-01 → today; one `getInfo`/export per site; small fixture CSV saved under `tests/fixtures/` |

## Week 3 (21–27 Nov): stage, dates, MWp

| ID | Status | Task | Done when |
|---|---|---|---|
| P5 | todo | `labels/`: panel / bare / vegetation / other points per park (**human-drawn**; agent prepares the notebook to draw them) | ≥ 50 points per class per park, source image date recorded |
| P6 | todo | `classify.py`: RF, fixed seed, leave-one-park-out training; class fractions per scene added to the CSV | Per held-out park: confusion matrix printed; fractions in CSV |
| P7 | todo | `stage.py` (pure) | Unit tests on fixture series: clean build, cloudy gap → `nesigur`, never-started, flicker not confirmed |
| P8 | todo | `mwp.py` (pure) + density factor calibration leave-one-park-out | Unit tests; calibration table per held-out park |
| P9 | todo | `evidence.py` + `run.py` writes `outputs/<site>.json` per `CONTRACT.md`; JSON-schema check in tests | Tismana 1 output validates; every stage change has ≥ 1 evidence row |
| P10 | todo | Time-lapse GIF per park (monthly clear composites) | 5 GIFs in `data/timelapse/`, paths in output |
| — | | **Intermediate presentation** (date TBC): demo P9 output for one TRACK + one CHECK park | |

## Week 4 (28 Nov–4 Dec): validation

| ID | Status | Task | Done when |
|---|---|---|---|
| P11 | todo | `/check-run` on all 6 parks; hand results to validation team (they own `validare/rezultate/`) | Metric table: stage accuracy, date error (days), MWp error % vs ±8%, panel IoU |
| P12 | todo | Fix the worst failure mode found in P11 (one change, re-run, decision note if params change) | Before/after table |
| P13 | todo | If MWp misses ±8%: switch reporting to interval only (README plan B), draft note for `docs/decizii/` | Decision note PR opened |

## Week 5 (5–11 Dec): freeze

| ID | Status | Task | Done when |
|---|---|---|---|
| P14 | todo | Freeze params; run all sites; export final outputs for backend import | Outputs carry the commit hash in `provenance` |
| P15 | todo | Update `pipeline/README.md` (English, short): add what each output field means; setup and run steps already there | Teammate can run one site from scratch following it |

## Later (not before 11 Dec)

VHR imagery for MWp and pile stage, BESS container counting, national-scale run over all ATR sites, Build-out Feed.
