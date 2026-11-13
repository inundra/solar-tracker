"""One logging setup for every CLI: INFO to console, DEBUG to data/logs/<site>_<ts>.log."""
import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"
FMT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(site: str, log_dir: Path = LOG_DIR) -> Path:
    """Configure the root logger (replacing earlier handlers) and return the log file path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{site}_{datetime.now():%Y%m%d-%H%M%S}.log"
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    file = logging.FileHandler(path, encoding="utf-8")
    file.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG, format=FMT, handlers=[console, file], force=True)
    return path
