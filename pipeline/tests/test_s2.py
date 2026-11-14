import math

import pytest

from src import ee_client, params, s2, sites


def _feat(date, idx, clear, ndvi=None):
    return {"properties": {"date": date, "system_index": idx, "product_id": f"P_{idx}", "tile": "34TFQ",
                           "clear_frac": clear, "ndvi": ndvi, "ndbi": None if ndvi is None else -0.1,
                           "bsi": None if ndvi is None else 0.05}}


FC = {"type": "FeatureCollection", "features": [
    _feat("2026-08-20", "b", 0.95, 0.3),
    _feat("2026-08-10", "a", 0.10),           # cloudy: no clear pixels → indices missing
    _feat("2026-08-15", "c", 0.80, 0.4),      # exactly at the threshold counts
]}


def test_to_frame_sorts_flags_obs_and_keeps_missing_indices():
    df = s2.to_frame(FC, min_clear_frac=0.80)
    assert list(df["system_index"]) == ["a", "c", "b"]
    assert list(df["obs"]) == [False, True, True]
    assert math.isnan(df.loc[0, "ndvi"])
    assert str(df["date"].dtype).startswith("datetime64")


def test_to_frame_empty():
    df = s2.to_frame({"type": "FeatureCollection", "features": []}, min_clear_frac=0.8)
    assert df.empty and "obs" in df.columns


def test_params_load():
    p = params.load()
    assert p["s2"]["clear_threshold"] == 0.60 and len(params.hash_()) == 12


@pytest.mark.ee
def test_scene_rows_ee_small_window():
    ee_client.init()
    p = params.load()
    fc = s2.scene_rows(sites.aoi(sites.get("tismana_1")), "2026-08-01", "2026-08-15", p).getInfo()
    df = s2.to_frame(fc, p["s2"]["min_clear_frac"])
    assert len(df) > 0 and df["clear_frac"].between(0, 1).all()
