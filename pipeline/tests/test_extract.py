from pathlib import Path

import pandas as pd
import pytest

from src import extract

P = {"s2": {"min_clear_frac": 0.8}, "s1": {"baseline_days": 90, "min_cover_frac": 0.95}}
SITE = {"id": "t", "s1_orbit": 7}
FIXTURE = Path(__file__).parent / "fixtures" / "tismana_1_sample.csv"


def _s2(date, idx, clear):
    return {"properties": {"sensor": "S2", "date": date, "system_index": idx, "product_id": "P", "tile": "34TFQ",
                           "csp_frac": 1.0, "clear_frac": clear, "ndvi": 0.3, "ndbi": 0.0, "bsi": 0.0}}


def _s1(date, idx):
    return {"properties": {"sensor": "S1", "date": date, "system_index": idx, "orbit": 7, "platform": "A",
                           "pass": "DESCENDING", "vv_sum": 10.0, "vv_count": 100, "vh_sum": 1.0, "vh_count": 100,
                           "cover_frac": 1.0}}


FC = {"type": "FeatureCollection", "features": [_s2("2026-01-05", "x", 0.9), _s1("2026-01-02", "r1"),
                                                 _s2("2026-01-01", "y", 0.1), _s1("2026-01-14", "r2")]}


def test_to_frame_splits_sensors_and_sorts():
    df = extract.to_frame(FC, P)
    assert list(df.columns) == extract.COLS
    assert list(df["sensor"]) == ["S2", "S1", "S2", "S1"]
    assert list(df["obs"]) == [False, True, True, True]
    assert df.loc[df.sensor == "S1", "vv_db"].tolist() == pytest.approx([-10.0, -10.0])


def test_save_load_roundtrip(tmp_path):
    df = extract.to_frame(FC, P)
    extract.save(df, {"params_hash": "abc"}, "t", tmp_path)
    back, meta = extract.load("t", tmp_path)
    pd.testing.assert_frame_equal(df.astype({"orbit": "Int64", "n_slices": "Int64"}), back, check_dtype=False)
    assert str(back["orbit"].dtype) == "Int64"
    assert back["obs"].dtype == bool and meta["params_hash"] == "abc"


def test_cache_used_unless_refresh(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(extract, "fetch", lambda *a: calls.append(1) or FC)
    monkeypatch.setattr(extract.params, "hash_", lambda: "h")
    first = extract.extract(SITE, "2026-01-01", "2026-02-01", P, refresh=False, ts_dir=tmp_path)
    again = extract.extract(SITE, "2026-01-01", "2026-02-01", P, refresh=False, ts_dir=tmp_path)
    extract.extract(SITE, "2026-01-01", "2026-02-01", P, refresh=True, ts_dir=tmp_path)
    assert len(calls) == 2 and len(first) == len(again) == 4


def test_missing_orbit_is_clear(tmp_path):
    with pytest.raises(ValueError, match="s1_orbit"):
        extract.extract({"id": "t"}, "2026-01-01", "2026-02-01", P, refresh=True, ts_dir=tmp_path)


def test_fixture_matches_schema():
    df, _ = extract.load("tismana_1_sample", FIXTURE.parent)
    assert list(df.columns) == extract.COLS and set(df["sensor"]) == {"S1", "S2"}
    assert FIXTURE.stat().st_size < 50_000
