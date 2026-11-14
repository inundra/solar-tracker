"""Sentinel-1 GRD per-date VV/VH over the AOI, one relative orbit per site, log-ratio vs a trailing baseline.

EE returns linear-power sums and pixel counts per scene; the pure part (to_frame) merges same-date slices,
converts to dB and computes the log-ratio. Averaging happens in linear power, never in dB.
CLI: python -m src.s1 --site tismana_1 --start 2026-05-01 --end 2026-11-01
"""
import argparse
import logging
import math

import numpy as np
import pandas as pd

from src import ee_client, params, sites
from src.log import setup_logging

S1 = "COPERNICUS/S1_GRD"
ROW = ["date", "system_index", "orbit", "platform", "pass", "vv_sum", "vv_count", "vh_sum", "vh_count", "cover_frac"]
OUT = ["date", "system_index", "orbit", "platform", "pass", "n_slices", "cover_frac", "obs",
       "vv_db", "vh_db", "vv_lr", "vh_lr"]
log = logging.getLogger(__name__)


def collection(aoi, start: str, end: str, p: dict, orbit: int | None = None):
    import ee

    col = (ee.ImageCollection(S1).filterBounds(aoi).filterDate(start, end)
           .filter(ee.Filter.eq("instrumentMode", p["s1"]["instrument_mode"]))
           .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
           .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")))
    return col if orbit is None else col.filter(ee.Filter.eq("relativeOrbitNumber_start", orbit))


def orbit_counts(aoi, start: str, end: str, p: dict):
    """ee.Dictionary {relative orbit: number of distinct dates}. Dates, not scenes: an AOI cut by a slice
    boundary gives two scenes per pass and would otherwise win the pick."""
    col = collection(aoi, start, end, p).map(lambda img: img.set("d", img.date().format("YYYY-MM-dd")))
    return col.distinct(["relativeOrbitNumber_start", "d"]).aggregate_histogram("relativeOrbitNumber_start")


def pick_orbit(counts: dict) -> int:
    """Orbit with the most scenes; ties go to the lowest orbit number so the choice is reproducible."""
    if not counts:
        raise ValueError("no Sentinel-1 scenes over the AOI in this date range")
    best = min(counts, key=lambda k: (-counts[k], int(float(k))))
    return int(float(best))


def scene_rows(aoi, start: str, end: str, orbit: int, p: dict):
    """ee.FeatureCollection, one feature per S1 scene of `orbit`. Nothing is fetched here."""
    import ee

    radius = p["s1"]["speckle_radius_m"]

    def row(img):
        crs = img.select("VV").projection()  # native 10 m grid; no scale literal needed
        db = img.select(["VV", "VH"])
        lin = db.multiply(math.log(10) / 10).exp().focalMedian(radius, "circle", "meters").rename(["vv", "vh"])
        stats = lin.reduceRegion(ee.Reducer.sum().combine(ee.Reducer.count(), sharedInputs=True),
                                 aoi, crs=crs, maxPixels=1e9)
        cover = lin.select("vv").mask().unmask(0).rename("cover_frac").reduceRegion(  # same mask as vv_count
            ee.Reducer.mean(), aoi, crs=crs, maxPixels=1e9)
        return ee.Feature(None, stats.combine(cover).combine({
            "date": img.date().format("YYYY-MM-dd"),
            "system_index": img.get("system:index"),
            "orbit": img.get("relativeOrbitNumber_start"),
            "platform": img.get("platform_number"),
            "pass": img.get("orbitProperties_pass"),
        }))

    return ee.FeatureCollection(collection(aoi, start, end, p, orbit).map(row))


def to_frame(fc: dict, baseline_days: int, min_cover_frac: float) -> pd.DataFrame:
    """getInfo() result → one row per date: VV/VH in dB and log-ratio (dB) vs the mean of the previous
    `baseline_days` (window [t - baseline_days, t), linear power). No earlier data → NaN."""
    raw = pd.DataFrame([f["properties"] for f in fc["features"]], columns=ROW)
    if raw.empty:
        return pd.DataFrame(columns=OUT)
    if raw["orbit"].nunique() > 1:
        raise ValueError(f"rows from several orbits {sorted(raw['orbit'].unique())}: mixing orbits fakes change")
    raw["date"] = pd.to_datetime(raw["date"])
    # a pass can cut the AOI into two slices with the same date: merge them pixel-weighted
    # shortcut: pixels where adjacent slices overlap are counted twice; mosaic per date server-side if split slices show up
    g = raw.sort_values("system_index").groupby(["date", "orbit"], as_index=False).agg(
        system_index=("system_index", "|".join), platform=("platform", "first"), **{"pass": ("pass", "first")},
        n_slices=("system_index", "size"), cover_frac=("cover_frac", "sum"),
        vv_sum=("vv_sum", "sum"), vv_count=("vv_count", "sum"), vh_sum=("vh_sum", "sum"), vh_count=("vh_count", "sum"))
    g["cover_frac"] = g["cover_frac"].clip(upper=1.0)
    ok = (g["cover_frac"] >= min_cover_frac).to_numpy()  # a partial pass sees a different area: not comparable
    g["obs"] = ok
    for b in ("vv", "vh"):
        lin = pd.Series((g[f"{b}_sum"] / g[f"{b}_count"]).to_numpy(), index=g["date"])
        base = lin.where(ok).rolling(f"{baseline_days}D", closed="left").mean()
        g[f"{b}_db"] = 10 * np.log10(lin.to_numpy())
        g[f"{b}_lr"] = np.where(ok, 10 * np.log10(lin.to_numpy() / base.to_numpy()), np.nan)
    return g[OUT]


def main(argv=None) -> pd.DataFrame:
    ap = argparse.ArgumentParser(prog="src.s1")
    ap.add_argument("--site", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True, help="exclusive")
    args = ap.parse_args(argv)
    try:
        site = sites.get(args.site)
        project = ee_client.init()
    except (KeyError, RuntimeError) as e:
        raise SystemExit(str(e))

    path = setup_logging(args.site)
    p = params.load()
    aoi = sites.aoi(site)
    log.info("site=%s log=%s params_hash=%s ee_project=%s", site["id"], path, params.hash_(), project)
    log.info("collection=%s mode=%s range=[%s, %s) speckle_radius_m=%s baseline_days=%s", S1,
             p["s1"]["instrument_mode"], args.start, args.end, p["s1"]["speckle_radius_m"], p["s1"]["baseline_days"])
    counts = orbit_counts(aoi, args.start, args.end, p).getInfo()
    orbit = site.get("s1_orbit") or pick_orbit(counts)  # fixed per site in sites.yaml; pick only if unset
    log.info("orbit_counts(dates)=%s orbit=%d (%s)", counts, orbit, "sites.yaml" if site.get("s1_orbit") else "picked")
    df = to_frame(scene_rows(aoi, args.start, args.end, orbit, p).getInfo(),
                  p["s1"]["baseline_days"], p["s1"]["min_cover_frac"])
    log.info("dates=%d obs=%d multi_slice_dates=%d min_cover=%.3f", len(df), int(df["obs"].sum()),
             int((df["n_slices"] > 1).sum()), df["cover_frac"].min() if len(df) else float("nan"))
    log.info("\n%s", df.to_string(index=False, float_format="%.2f"))
    return df


if __name__ == "__main__":
    main()
