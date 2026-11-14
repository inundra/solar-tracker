"""CLI entry: python -m src.run --site <id> [--dry] [--refresh]. Stages are wired in from P1 on."""
import argparse
import logging
from pathlib import Path

from src import ee_client, params, sites
from src.log import LOG_DIR, setup_logging

log = logging.getLogger(__name__)


def main(argv=None, log_dir: Path = LOG_DIR) -> None:
    ap = argparse.ArgumentParser(prog="src.run")
    ap.add_argument("--site", required=True)
    ap.add_argument("--dry", action="store_true", help="init EE and report the AOI, extract no data")
    ap.add_argument("--refresh", action="store_true", help="re-extract instead of using cache")
    args = ap.parse_args(argv)
    try:
        site = sites.get(args.site)  # before logging: the id becomes part of the log file name
    except KeyError as e:
        ap.error(str(e))
    try:
        project = ee_client.init()  # before logging: a failed start leaves no empty log
    except RuntimeError as e:
        raise SystemExit(str(e))

    path = setup_logging(args.site, log_dir)
    log.info("site=%s (%s, %s) dry=%s refresh=%s log=%s",
             site["id"], site["name"], site["role"], args.dry, args.refresh, path)
    log.info("params_hash=%s", params.hash_())
    log.info("ee_project=%s", project)
    log.info("aoi_area_ha=%.1f", sites.area_ha(site))
    if args.dry:
        log.info("dry run: stopping before data extraction")
        return
    raise SystemExit("only --dry is implemented so far (P1+)")


if __name__ == "__main__":
    main()
