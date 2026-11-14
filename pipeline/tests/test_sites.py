import pytest

from src import ee_client, sites
from src.run import main


def test_load_all_sites_have_role_and_geometry():
    all_sites = sites.load()
    ids = [s["id"] for s in all_sites]
    assert len(ids) == 6 and len(set(ids)) == 6
    assert {s["role"] for s in all_sites} == {"TRACK", "CHECK"}
    assert all(s["geometry"] for s in all_sites)


def test_get_known_and_unknown():
    assert sites.get("isalnita")["name"] == "Ișalnița"  # diacritics survive utf-8 load
    with pytest.raises(KeyError, match="tismana_1"):
        sites.get("../x")


def test_unknown_site_rejected_before_logging(tmp_path):
    with pytest.raises(SystemExit):
        main(["--site", "../x", "--dry"], log_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_missing_ee_project_is_clear(monkeypatch):
    monkeypatch.delenv("EE_PROJECT", raising=False)
    with pytest.raises(RuntimeError, match="EE_PROJECT"):
        ee_client.init()


@pytest.mark.ee
def test_tismana_1_area_ee():
    ee_client.init()
    assert 400 < sites.area_ha(sites.get("tismana_1")) < 470  # LOG: ~434 ha
