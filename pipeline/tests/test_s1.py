import math

import pytest

from src import ee_client, params, s1, sites


def _feat(date, idx, vv_lin, vh_lin, n=100, cover=1.0, orbit=7):
    return {"properties": {"date": date, "system_index": idx, "orbit": orbit, "platform": "A", "pass": "ASCENDING",
                           "vv_sum": vv_lin * n, "vv_count": n, "vh_sum": vh_lin * n, "vh_count": n,
                           "cover_frac": cover}}


def _fc(*feats):
    return {"type": "FeatureCollection", "features": list(feats)}


def test_pick_orbit_most_scenes_then_lowest_number():
    assert s1.pick_orbit({"80": 30, "7": 30, "153": 12}) == 7
    assert s1.pick_orbit({"153": 31, "7": 30}) == 153
    with pytest.raises(ValueError):
        s1.pick_orbit({})


def test_db_and_log_ratio_vs_previous_window():
    df = s1.to_frame(_fc(
        _feat("2026-01-01", "a", 0.1, 0.01),
        _feat("2026-01-13", "b", 0.1, 0.01),
        _feat("2026-01-25", "c", 1.0, 0.01),     # 10x VV power = +10 dB vs baseline
        _feat("2026-06-01", "d", 0.1, 0.01),     # nothing in the 90 days before → no baseline
    ), baseline_days=90, min_cover_frac=0.95)
    assert list(df["system_index"]) == ["a", "b", "c", "d"]
    assert df.loc[0, "vv_db"] == pytest.approx(-10.0)
    assert math.isnan(df.loc[0, "vv_lr"])                     # first date: no baseline
    assert df.loc[1, "vv_lr"] == pytest.approx(0.0)
    assert df.loc[2, "vv_lr"] == pytest.approx(10.0)
    assert df.loc[2, "vh_lr"] == pytest.approx(0.0)
    assert math.isnan(df.loc[3, "vv_lr"])


def test_same_date_slices_merge_pixel_weighted():
    df = s1.to_frame(_fc(
        _feat("2026-01-01", "s1", 0.1, 0.01, n=300, cover=0.75),
        _feat("2026-01-01", "s2", 0.5, 0.01, n=100, cover=0.30),
    ), baseline_days=90, min_cover_frac=0.95)
    assert len(df) == 1
    assert df.loc[0, "vv_db"] == pytest.approx(10 * math.log10((0.1 * 300 + 0.5 * 100) / 400))
    assert df.loc[0, "cover_frac"] == 1.0 and df.loc[0, "n_slices"] == 2
    assert df.loc[0, "system_index"] == "s1|s2"


def test_mixed_orbits_rejected():
    with pytest.raises(ValueError, match="orbits"):
        s1.to_frame(_fc(_feat("2026-01-01", "a", 0.1, 0.01, orbit=7),
                        _feat("2026-01-13", "b", 0.1, 0.01, orbit=29)), baseline_days=90, min_cover_frac=0.95)


def test_empty():
    assert s1.to_frame(_fc(), baseline_days=90, min_cover_frac=0.95).empty


@pytest.mark.ee
def test_s1_ee_small_window():
    ee_client.init()
    p = params.load()
    aoi = sites.aoi(sites.get("tismana_1"))
    orbit = s1.pick_orbit(s1.orbit_counts(aoi, "2026-08-01", "2026-09-01", p).getInfo())
    df = s1.to_frame(s1.scene_rows(aoi, "2026-08-01", "2026-09-01", orbit, p).getInfo(), p["s1"]["baseline_days"], p["s1"]["min_cover_frac"])
    assert len(df) > 0 and (df["orbit"] == orbit).all() and df["vv_db"].between(-30, 5).all()


def test_partial_cover_is_not_an_obs_and_stays_out_of_baseline():
    df = s1.to_frame(_fc(
        _feat("2026-01-01", "a", 0.1, 0.01),
        _feat("2026-01-13", "b", 1.0, 0.01, cover=0.5),   # half the AOI: not comparable
        _feat("2026-01-25", "c", 0.1, 0.01),
    ), baseline_days=90, min_cover_frac=0.95)
    assert list(df["obs"]) == [True, False, True]
    assert math.isnan(df.loc[1, "vv_lr"])
    assert df.loc[2, "vv_lr"] == pytest.approx(0.0)       # baseline ignores the partial pass
