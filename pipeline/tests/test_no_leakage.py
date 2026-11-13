"""Hard rule 1: nothing in src/, labels/ or config/ may reference the ground-truth folder."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDED = ["src", "labels", "config"]


def test_no_reference_to_ground_truth():
    hits = [
        str(p.relative_to(ROOT))
        for d in GUARDED
        for p in (ROOT / d).rglob("*")
        if p.is_file() and "validare" in p.read_bytes().decode("utf-8", "ignore").lower()
    ]
    assert not hits, f"files mention the ground-truth folder: {hits}"
