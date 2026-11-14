"""Per-site time-series cache: S2 scenes and S1 dates in one CSV, fetched with one getInfo per site.

data/timeseries/<site>.csv       one row per S2 scene (sensor=S2) or S1 date (sensor=S1), sorted by date
data/timeseries/<site>.meta.json provenance: date range, collections, S1 orbit, params hash, extraction time
CLI: python -m src.extract --site tismana_1 [--refresh] | --all [--refresh]
"""
import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src import ee_client, params, s1, s2, sites
from src.log import setup_logging

TS_DIR = Path(__file__).resolve().parents[1] / "data" / "timeseries"
COLS = ["sensor", "date", "system_index", "product_id", "tile", "orbit", "platform", "pass", "n_slices",
        "cover_frac", "csp_frac", "clear_frac", "obs", "ndvi", "ndbi", "bsi", "vv_db", "vh_db", "vv_lr", "vh_lr"]
log = logging.getLogger(__name__)


def fetch(site: dict, start: str, end: str, p: dict) -> dict:
    """The one EE round trip per site: S2 and S1 rows merged server-side."""
    aoi = sites.aoi(site)
    s2fc = s2.scene_rows(aoi, start, end, p).map(lambda f: f.set("sensor", "S2"))
    s1fc = s1.scene_rows(aoi, start, end, site["s1_orbit"], p).map(lambda f: f.set("sensor", "S1"))
    return s2fc.merge(s1fc).getInfo()


def to_frame(fc: dict, p: dict) -> pd.DataFrame:
    """Merged getInfo() result → one table; S2 and S1 rows go through their own pure converters."""
    part = {k: {"features": [f for f in fc["features"] if f["properties"]["sensor"] == k]} for k in ("S2", "S1")}
    d2 = s2.to_frame(part["S2"], p["s2"]["min_clear_frac"]).assign(sensor="S2")
    d1 = s1.to_frame(part["S1"], p["s1"]["baseline_days"], p["s1"]["min_cover_frac"]).assign(sensor="S1")
    frames = [d for d in (d2, d1) if not d.empty]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLS)
    return df.reindex(columns=COLS).sort_values(["date", "sensor"], ascending=[True, False],
                                                kind="stable").reset_index(drop=True)


def save(df: pd.DataFrame, meta: dict, site_id: str, ts_dir: Path = TS_DIR) -> Path:
    ts_dir.mkdir(parents=True, exist_ok=True)
    path = ts_dir / f"{site_id}.csv"
    df.to_csv(path, index=False, encoding="utf-8", date_format="%Y-%m-%d")
    with open(ts_dir / f"{site_id}.meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return path


def load(site_id: str, ts_dir: Path = TS_DIR) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(ts_dir / f"{site_id}.csv", encoding="utf-8", parse_dates=["date"])
    df["obs"] = df["obs"].astype(bool)
    df[["orbit", "n_slices"]] = df[["orbit", "n_slices"]].astype("Int64")  # empty on S2 rows
    meta_path = ts_dir / f"{site_id}.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return df, meta


def extract(site: dict, start: str, end: str, p: dict, refresh: bool = False, ts_dir: Path = TS_DIR) -> pd.DataFrame:
    if not site.get("s1_orbit"):
        raise ValueError(f"site {site['id']!r} has no s1_orbit in sites.yaml; pick it once over the full range")
    if not refresh and (ts_dir / f"{site['id']}.csv").exists():
        df, meta = load(site["id"], ts_dir)
        log.info("cache hit: %s rows=%d range=%s extracted_at=%s", site["id"], len(df),
                 meta.get("date_range"), meta.get("extracted_at"))
        if meta.get("params_hash") != params.hash_():
            log.warning("cache made with params_hash=%s, current=%s: rerun with --refresh",
                        meta.get("params_hash"), params.hash_())
        if meta.get("s1_orbit") != site["s1_orbit"] or (meta.get("date_range") or [None])[0] != start:
            log.warning("cache made with s1_orbit=%s start=%s, requested %s / %s: rerun with --refresh",
                        meta.get("s1_orbit"), (meta.get("date_range") or [None])[0], site["s1_orbit"], start)
        return df
    df = to_frame(fetch(site, start, end, p), p)
    meta = {"site_id": site["id"], "date_range": [start, end], "end_exclusive": True,
            "collections": [s2.S2, s2.CSP, s1.S1], "s1_orbit": site["s1_orbit"], "params_hash": params.hash_(),
            "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    path = save(df, meta, site["id"], ts_dir)
    log.info("extracted %s -> %s", site["id"], path)
    return df


def summary(df: pd.DataFrame) -> str:
    s2r, s1r = df[df.sensor == "S2"], df[df.sensor == "S1"]
    return (f"S2 scenes={len(s2r)} clear_obs={int(s2r.obs.sum())} | S1 dates={len(s1r)} obs={int(s1r.obs.sum())} "
            f"| first={df.date.min():%Y-%m-%d} last={df.date.max():%Y-%m-%d}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="src.extract")
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--site")
    who.add_argument("--all", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="re-extract instead of using the cache")
    ap.add_argument("--start", help="default: params start_date")
    ap.add_argument("--end", help="exclusive; default: tomorrow")
    args = ap.parse_args(argv)
    p = params.load()
    start, end = args.start or p["start_date"], args.end or str(date.today() + timedelta(days=1))
    try:
        todo = sites.load() if args.all else [sites.get(args.site)]
        project = ee_client.init()
    except (KeyError, RuntimeError) as e:
        raise SystemExit(str(e))

    for site in todo:
        path = setup_logging(site["id"])
        log.info("site=%s log=%s params_hash=%s ee_project=%s range=[%s, %s) s1_orbit=%s refresh=%s",
                 site["id"], path, params.hash_(), project, start, end, site.get("s1_orbit"), args.refresh)
        df = extract(site, start, end, p, refresh=args.refresh)
        log.info("%s: %s", site["id"], summary(df))


if __name__ == "__main__":
    main()
