import logging

import pytest

from src.log import setup_logging
from src.run import main


@pytest.fixture(autouse=True)
def _close_log_handlers():
    yield
    logging.basicConfig(force=True, handlers=[logging.NullHandler()])  # releases the file on Windows


def test_dry_run_writes_utf8_log_file(tmp_path):
    main(["--site", "tismana_1", "--dry"], log_dir=tmp_path)
    logging.getLogger().info("stadiu: în construcție")
    files = list(tmp_path.glob("tismana_1_*.log"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "params_hash=" in text and "în construcție" in text


def test_setup_is_idempotent(tmp_path):
    setup_logging("a", log_dir=tmp_path)
    setup_logging("b", log_dir=tmp_path)
    assert len(logging.getLogger().handlers) == 2  # console + one file, not stacked
