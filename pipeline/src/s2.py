"""Sentinel-2 per-scene rows: Cloud Score+ clear fraction over the AOI and mean indices over clear pixels.

EE builds one FeatureCollection server-side (one row per scene); to_frame() is the pure part.
CLI: python -m src.s2 --site tismana_1 --start 2026-08-01 --end 2026-11-01
"""
import argparse
import logging

import pandas as pd

from src import ee_client, params, sites
from src.log import setup_logging

S2 = "COPERNICUS/S2_SR_HARMONIZED"
CSP = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
COLS = ["date", "system_index", "product_id", "tile", "csp_frac", "clear_frac", "ndvi", "ndbi", "bsi"]
NUM = ["csp_frac", "clear_frac", "ndvi", "ndbi", "bsi"]
BSI = "((b('B11') + b('B4')) - (b('B8') + b('B2'))) / ((b('B11') + b('B4')) + (b('B8') + b('B2')))"
log = logging.getLogger(__name__)


def collection(aoi, start: str, end: str):
    import ee

    return (ee.ImageCollection(S2).filterBounds(aoi).filterDate(start, end)
            .linkCollection(ee.ImageCollection(CSP), ["cs_cdf"]))


def scene_rows(aoi, start: str, end: str, p: dict):
    """ee.FeatureCollection, one feature per S2 scene touching the AOI. Nothing is fetched here."""
    import ee

    th, scale = p["s2"]["clear_threshold"], p["s2"]["scale_m"]

    def row(img):
        crs = img.select("B4").projection()  # reduce on the scene's own 10 m UTM grid
        cs = img.select("cs_cdf")
        # masked / outside the scene footprint counts as not clear, so partial tiles get a low clear_frac;
        # csp_frac separates "no Cloud Score+ / off footprint" (0) from "overcast" (csp_frac > 0, clear_frac 0)
        clear = cs.gte(th).unmask(0).rename("clear_frac")
        fracs = ee.Image.cat(clear, cs.mask().unmask(0).rename("csp_frac")).reduceRegion(
            ee.Reducer.mean(), aoi, scale, crs=crs, maxPixels=1e9)
        idx = ee.Image.cat(
            img.normalizedDifference(["B8", "B4"]).rename("ndvi"),
            img.normalizedDifference(["B11", "B8"]).rename("ndbi"),
            img.expression(BSI).rename("bsi"),
        ).updateMask(clear)
        means = idx.reduceRegion(ee.Reducer.mean(), aoi, scale, crs=crs, maxPixels=1e9)
        return ee.Feature(None, means.combine(fracs).combine({
            "date": img.date().format("YYYY-MM-dd"),
            "system_index": img.get("system:index"),
            "product_id": img.get("PRODUCT_ID"),
            "tile": img.get("MGRS_TILE"),
        }))

    return ee.FeatureCollection(collection(aoi, start, end).map(row))


def thumb_urls(aoi, system_index: str, p: dict, dims: int = 512) -> dict:
    """PNG URLs for a visual spot-check of one scene: true colour, and the clear mask (white = clear).
    Display-only: the buffer, stretch, size and search dates here never affect results."""
    import ee

    img = collection(aoi, "2015-06-01", "2100-01-01").filter(ee.Filter.eq("system:index", system_index)).first()
    region = aoi.buffer(300).bounds()
    clear = ee.Image(0.5).blend(img.select("cs_cdf").gte(p["s2"]["clear_threshold"]).unmask(0).clip(aoi))  # grey = outside AOI
    return {
        "rgb": img.visualize(bands=["B4", "B3", "B2"], min=0, max=3000)
                  .blend(ee.Image().paint(aoi, 0, 2).visualize(palette=["ffff00"]))  # AOI outline
                  .getThumbURL({"region": region, "dimensions": dims}),
        "clear": clear.visualize(min=0, max=1).getThumbURL({"region": region, "dimensions": dims}),
    }


def to_frame(fc: dict, min_clear_frac: float) -> pd.DataFrame:
    """getInfo() result → one row per scene, sorted by date; obs = scene counts as a clear observation."""
    df = pd.DataFrame([f["properties"] for f in fc["features"]], columns=COLS)
    df["date"] = pd.to_datetime(df["date"])
    df[NUM] = df[NUM].astype(float)  # None (no clear pixels) → NaN
    df["obs"] = df["clear_frac"] >= min_clear_frac
    return df.sort_values(["date", "system_index"]).reset_index(drop=True)


def main(argv=None) -> pd.DataFrame:
    ap = argparse.ArgumentParser(prog="src.s2")
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
    log.info("site=%s log=%s params_hash=%s ee_project=%s", site["id"], path, params.hash_(), project)
    log.info("collections=%s + %s[cs_cdf] range=[%s, %s) clear_threshold=%s min_clear_frac=%s",
             S2, CSP, args.start, args.end, p["s2"]["clear_threshold"], p["s2"]["min_clear_frac"])
    df = to_frame(scene_rows(sites.aoi(site), args.start, args.end, p).getInfo(), p["s2"]["min_clear_frac"])
    log.info("scenes=%d clear_obs=%d no_cloudscore=%d", len(df), int(df["obs"].sum()), int((df["csp_frac"] == 0).sum()))
    log.info("\n%s", df.to_string(index=False, float_format="%.3f"))
    return df


if __name__ == "__main__":
    main()
