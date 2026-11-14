# Pipeline agent brief (MWitness / solar-tracker)

You work on `pipeline/` only. Read this file fully before any task, then `APPROACH.md` (what we do now and why) and the top 3 entries of `LOG.md` (what happened recently). Repo-wide docs are in Romanian; `pipeline/` docs (README included), code, comments and commit messages are in English.

## Records you keep (part of every task, not optional)

- **`LOG.md`**: append-only work log, newest entry at the top, using the template in the file. One entry per task, check-run or notable finding: what was done, **why**, the numbers, what's unchecked, what's next, the commit.
- **`APPROACH.md`**: the current approach as a living doc. Rewrite the affected rows/sections when a task changes *what* the pipeline does or *why*; bump "Last updated". When something is replaced, mark it `replaced` and put the reason in `LOG.md`. Keep it a 5-minute read.
- **Run logs**: `run.py` and `extract.py` use Python `logging` (INFO to console, DEBUG to `data/logs/<site>_<YYYYmmdd-HHMMSS>.log`, `encoding="utf-8"`). Log params hash, collection IDs, date range, scene counts, clear-obs counts, and every stage decision with its evidence ID. Never log secrets. Cite the run-log path in the `LOG.md` entry.

## Mission

For each solar / BESS project, from Sentinel imagery, produce:
- **stage per date**: `neînceput`, `în construcție`, `construit`, `nesigur` (exact strings, UTF-8),
- **clearing date** and **modules-appear date**,
- **MWp** estimate (as an interval) and an **MWac** interval,
- an **evidence log**: every claim cites image date, product, tile / `system:index`, clear fraction.

Output format is fixed by `CONTRACT.md`. Deadline 11 Dec 2026; plan in `BACKLOG.md`.

Study areas (`config/sites.yaml`):
- TRACK (under construction, follow progress): Tismana 1, Tismana 2, Rovinari (Gorj), Ișalnița (Dolj)
- CHECK (finished, known MWp and dates, verify the model): Văcărești, Titu
  > The repo README lists Dâmbovița + Giurgiu as CHECK counties; confirm with the human which park is in Giurgiu before assuming.

## Hard rules (never break; stop and ask instead)

1. **Ground truth is not training data.** Nothing in `src/`, `labels/` or `config/` may read, copy or derive from `../validare/`. Only the `/check-run` evaluation may read `../validare/proiecte_cartate/`, read-only. A test enforces this (`tests/test_no_leakage.py`).
2. **Leave-one-park-out** for anything fitted (classifier, thresholds, MWp density factor): fit on the other parks, evaluate on the held-out one. Never report a metric on a park that was used to fit.
3. **No data in git**: no rasters, GeoTIFF, `.zip`, `.nc`, big CSVs. Cache goes to `pipeline/data/`, outputs to `pipeline/outputs/` (both gitignored, set up in P0). Small fixtures (< 50 KB) under `tests/fixtures/` are fine.
4. **No secrets**: never read or print `.env`, `credentials*.json`, `~/.config/earthengine/`. The EE project comes from env var `EE_PROJECT`.
5. **Stay in `pipeline/`.** Changes to `backend/`, `validare/`, `business/`, root files go through a PR reviewed by that team: propose them, don't make them.
6. **Notebooks**: clear outputs before commit (`nbstripout <file>`). Reusable code goes to `src/`, not notebooks.
7. **Every threshold lives in `config/params.yaml`.** No magic numbers in code. Changing a value that changes reported results → draft a short note for `../docs/decizii/YYYY-MM-DD_<topic>.md` (outside `pipeline/`: ask first).
8. **Git**: branch `pipeline/<short-desc>`, small commits. Ask before `git push` and before opening a PR. Never commit to `main`.
9. **Windows**: always `open(..., encoding="utf-8")`; the stage strings and park names have diacritics.

When unsure, say "uncertain" rather than guess. That is literally a product value (`nesigur`).

## Architecture

Earth Engine extracts numbers. Pure Python decides. Keep that split.

```
src/
  ee_client.py     init(): ee.Initialize(project=os.environ["EE_PROJECT"]); clear error if unset/unauthenticated
  sites.py         load config/sites.yaml → list of {id, name, role, county, geometry(ee.Geometry)}
  s2.py            S2 SR harmonized + Cloud Score+ link, mask cs_cdf >= params, indices (NDVI, NDBI, BSI)
  s1.py            S1 GRD IW VV+VH, single relative orbit per site, speckle filter, log-ratio vs baseline
  extract.py       per site × per scene → one row: date, product, system:index, clear_frac, class fractions, indices, VV/VH
                   writes data/timeseries/<site_id>.csv (cache; re-extract only with --refresh)
  classify.py      RandomForest (ee.Classifier.smileRandomForest, fixed seed): panel / bare / vegetation / other,
                   trained on labels/*.geojson of the training parks only
  stage.py         PURE: time series DataFrame → stage per date, clearing_date, modules_date
  mwp.py           PURE: panel area → MWp interval (density factor range) → MWac interval (DC/AC range)
  evidence.py      PURE: builds evidence rows for each claim
  run.py           CLI: python -m src.run --site tismana_1 [--refresh] → outputs/<site_id>.json (per CONTRACT.md)
tests/             pytest; pure modules tested offline with fixture CSVs; EE code smoke-tested behind marker `ee`
labels/            small hand-drawn training GeoJSON (pipeline team), per park
notebooks/         exploration only
```

### Earth Engine specifics

- Sentinel-2: `COPERNICUS/S2_SR_HARMONIZED`. Cloud Score+: `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`, band `cs_cdf`, `s2.linkCollection(csp, ["cs_cdf"])`, keep pixels with `cs_cdf >= s2.clear_threshold` (0.60).
- Per scene, compute `clear_frac` over the AOI; a scene counts as an observation only if `clear_frac >= s2.min_clear_frac`.
- Sentinel-1: `COPERNICUS/S1_GRD`, `instrumentMode == "IW"`, both `VV` and `VH`, one `relativeOrbitNumber_start` per site (mixing orbits fakes change). Values are already dB.
- Use `reduceRegion(scale=10, maxPixels=1e9)` mapped over the collection to build a FeatureCollection of rows server-side, then one `getInfo()` / export per site. **Never `getInfo()` inside a Python loop over scenes.**
- Seeds fixed (`seed` in params). Record collection IDs and date ranges in each output (`CONTRACT.md` → `provenance`).
- Time-lapse: `ImageCollection.getVideoThumbURL` on monthly clear composites; save GIFs to `data/timelapse/`, never commit.

### Decision logic (stage.py), all thresholds from params

- `clearing_date`: first date where vegetation fraction drops by ≥ `veg_drop` vs the site baseline AND bare fraction ≥ `bare_min`, confirmed by `confirm_n` consecutive clear observations.
- `modules_date`: first date where panel fraction ≥ `panel_min`, confirmed the same way.
- Stage at date t: `construit` if panel fraction ≥ `built_frac` × final plateau; `în construcție` if after clearing; else `neînceput`.
- `nesigur` if fewer than `min_obs_window` clear S2 observations in the last `window_days` **and** S1 change is not decisive (`|log_ratio| < s1.decisive_db`). Prefer `nesigur` over a wrong confident stage.
- Dates are reported as an interval `[last_obs_before, first_obs_confirming]`, never a single day pretending precision.

### MWp (mwp.py)

- Panel area from the classified mask at 10 m covers whole array rows including gaps, so convert with a **density factor (MWp per ha of mapped array)** calibrated leave-one-park-out, not a nameplate W/m².
- Output MWp as `[low, high]` (README plan B: interval if ±8% is not reached). MWac = MWp / DC-AC ratio range from params.

## Definition of done (every task)

- [ ] Tests written first for pure logic; `python -m pytest -q` green.
- [ ] Ran on one TRACK park end to end (smallest date range that shows the behaviour); output validates against `CONTRACT.md`.
- [ ] `pipeline-reviewer` subagent ran on the diff; blocking findings fixed.
- [ ] No data files, no notebook outputs, no secrets in `git diff --cached`.
- [ ] `BACKLOG.md` item status updated, with a one-line note of what changed.
- [ ] `LOG.md` entry added (done / why / result / not checked / next / commit).
- [ ] `APPROACH.md` updated if the approach, a reason, or the current results changed.

## Commands

```
python -m pytest -q                       # offline tests
python -m pytest -q -m ee                 # EE smoke tests (needs auth)
python -m src.run --site <id> [--refresh]
nbstripout notebooks/*.ipynb
```

## When to stop and ask the human

- `EE_PROJECT` unset or `ee.Initialize` fails (they must run `earthengine authenticate`).
- A choice that changes reported numbers (thresholds, density factor, label set).
- Anything outside `pipeline/`, anything touching `validare/`, push / PR.
- Contract changes (backend and validation teams consume it).
- Metrics look too good (likely leakage), or a park has no usable clear observations.
