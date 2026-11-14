"""config/params.yaml: the one place thresholds come from."""
import hashlib
from pathlib import Path

import yaml

PATH = Path(__file__).resolve().parents[1] / "config" / "params.yaml"


def load(path: Path = PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def hash_(path: Path = PATH) -> str:
    """Short hash logged with every run so results can be tied to the params that made them."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
