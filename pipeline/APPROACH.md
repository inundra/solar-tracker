# Pipeline approach (living document)

**Last updated:** 2026-11-14 · **by:** P4 extraction · **backlog at:** P4 done (Week 2 data path complete), P5 next (labels, human-drawn)

> This file describes the approach **as it is right now**. Rewrite sections when the approach changes. Don't append history here; history goes in `LOG.md`.
> Update it at the end of every task that changes *what* the pipeline does or *why*. Keep it readable in 5 minutes by a teammate who missed a week.

## 1. Goal in one paragraph

For each solar / BESS project, use Sentinel-2 (optical) and Sentinel-1 (radar) to report the construction stage over time (`neînceput`, `în construcție`, `construit`, `nesigur`), the clearing and modules dates, MWp / MWac intervals, and an evidence log citing every image used. Output per `CONTRACT.md`, deadline 11 Dec 2026.

## 2. Current approach, step by step

| # | Step | How (current) | Why this way | Status |
|---|---|---|---|---|
| 1 | Sites | Hand-drawn AOIs in `config/sites.yaml` (fence + ~200 m) | Backend site geometry not ready yet; GT polygons in `validare/` are off-limits | working (P1: loaded by `src/sites.py`, area checked in EE) |
| 2 | Optical data | S2 SR harmonized, Cloud Score+ `cs_cdf ≥ 0.60`, scene kept if ≥ 80% of AOI clear | Cloud Score+ is the README's chosen mask; partial-cloud scenes give false fractions | working (P2: `src/s2.py`; no-data counts as not clear) |
| 3 | Radar data | S1 GRD IW VV/VH, one relative orbit per site **fixed in `sites.yaml` (`s1_orbit`)**, log-ratio vs 90-day baseline; a pass counts only if it covers ≥ 95% of the AOI (`s1.min_cover_frac`) | Fills cloudy weeks; mixing orbits creates fake change; orbit picked once by most distinct dates 2022→2026 so a different date range can't switch it; partial passes see a different area | working (P3/P4) |
| 4 | Extraction | One server-side FeatureCollection (S2 scenes + S1 dates) per site, one `getInfo` → `data/timeseries/<site>.csv` + `.meta.json` (provenance); cached, `--refresh` to redo | Cheap on quota; decision logic becomes testable offline | working (P4: all 6 sites, 2022-01-01 → 2026-11-13) |
| 5 | Classification | RF (panel / bare / vegetation / other), leave-one-park-out | Simple, explainable, works with few labels | planned |
| 6 | Stage + dates | Pure Python rules on fractions, confirmed by N clear obs, dates as intervals | Explainable to clients; intervals are honest about revisit gaps | planned |
| 7 | MWp | Panel area × density factor (MWp/ha) calibrated leave-one-park-out; reported as interval | 10 m pixels include row gaps, so a calibrated factor beats nameplate W/m² | planned |
| 8 | Evidence | Every stage change cites image date, product, image ID, tile, clear fraction | Core product promise: "dated evidence report" | planned |

Status values: `planned` / `in progress` / `working` / `replaced` (say by what; reason in LOG).

## 3. Current results

_None yet._ After each `/check-run`, replace this with the latest summary (mean stage accuracy, date error, MWp rel. error vs ±8%, # `nesigur`) and the date / commit it came from.

## 4. Known limitations and risks

- Labels are hand-drawn by the pipeline team; quality and quantity are still unknown.
- 6 parks is a small sample: metrics will be noisy.
- Thin haze can pass Cloud Score+ at `cs_cdf ≥ 0.60`: Tismana 1 on 2026-10-09 and 2026-10-17 counted as clear (1.000, 0.916) with NDVI 0.24 / 0.21 vs ~0.37 around them. AOI buffers also hold farmland with seasonal NDVI swings. `confirm_n` should absorb single dips; tightening `clear_threshold` is a human decision.
- Single S1 dates can jump > `decisive_db` (1.5 dB) and fall back next pass (Tismana 1: +2.3 dB 2026-05-12, +2.5 dB 2026-10-22, likely wet soil). S1 change needs confirming over consecutive passes before it counts as decisive (P7).
- Where a pass splits the AOI across two S1 slices, overlap pixels count twice (Tismana 2: 15 dates, Rovinari: 6); small bias, marked `shortcut:` in `s1.py`.
- MWp at 10 m may not reach ±8% → plan B: report the interval only.

## 5. Open questions (owner)

- Which CHECK park is in Giurgiu? (team lead)
- Who draws training labels, and when? (pipeline team)
- `CONTRACT.md` sign-off (backend + validation)
- Which public sources count for developer-reported MWp? (validation)

## 6. Rejected alternatives (and why)

- **openEO / CDSE as the main platform**: no Cloud Score+; would need another cloud mask. Kept as a fallback only.
- **Decision logic inside Earth Engine**: hard to unit-test and expensive to iterate on.
