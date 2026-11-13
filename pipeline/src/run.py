"""CLI entry: python -m src.run --site <id> [--dry] [--refresh]. Stages are wired in from P1 on."""
import argparse
import hashlib
import logging
from pathlib import Path

from src.log import LOG_DIR, setup_logging

PARAMS = Path(__file__).resolve().parents[1] / "config" / "params.yaml"
log = logging.getLogger(__name__)


def main(argv=None, log_dir: Path = LOG_DIR) -> None:
    ap = argparse.ArgumentParser(prog="src.run")
    ap.add_argument("--site", required=True)
    ap.add_argument("--dry", action="store_true", help="set up and log, touch no data")
    ap.add_argument("--refresh", action="store_true", help="re-extract instead of using cache")
    args = ap.parse_args(argv)

    path = setup_logging(args.site, log_dir)
    log.info("site=%s dry=%s refresh=%s log=%s", args.site, args.dry, args.refresh, path)
    log.info("params_hash=%s", hashlib.sha256(PARAMS.read_bytes()).hexdigest()[:12])
    if args.dry:
        log.info("dry run: stopping before any Earth Engine call")
        return
    raise SystemExit("only --dry is implemented so far (P1+)")


if __name__ == "__main__":
    main()
