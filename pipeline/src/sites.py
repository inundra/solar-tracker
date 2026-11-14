"""Load config/sites.yaml. Geometry stays raw [lon, lat] rings; aoi() turns it into an ee.Geometry."""
from pathlib import Path

import yaml

SITES = Path(__file__).resolve().parents[1] / "config" / "sites.yaml"


def load(path: Path = SITES) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["sites"]


def get(site_id: str, path: Path = SITES) -> dict:
    all_sites = load(path)
    for s in all_sites:
        if s["id"] == site_id:
            return s
    raise KeyError(f"unknown site {site_id!r}; valid: {', '.join(s['id'] for s in all_sites)}")


def aoi(site: dict):
    import ee

    if not site.get("geometry"):
        raise ValueError(f"site {site['id']!r} has no geometry in sites.yaml")
    return ee.Geometry.Polygon(site["geometry"])


def area_ha(site: dict) -> float:
    return aoi(site).area(maxError=1).getInfo() / 1e4  # one call per site, not per scene
