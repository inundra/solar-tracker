"""Hard rule 1: nothing in src/, labels/ or config/ may reference the ground-truth folder."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDED = ["src", "labels", "config"]
MARKERS = ["validare", "proiecte_cartate"]  # folder and GT subfolder; either name alone is enough


def test_no_reference_to_ground_truth():
    hits = [
        str(p.relative_to(ROOT))
        for d in GUARDED
        for p in (ROOT / d).rglob("*")
        if p.is_file() and any(m in p.read_bytes().decode("utf-8", "ignore").lower() for m in MARKERS)
    ]
    assert not hits, f"files mention the ground-truth folder: {hits}"
