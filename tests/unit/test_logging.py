import logging
from datetime import date

import pytest

from infrastructure.config import logging as log_config
from infrastructure.config.logging import DailyFileHandler, setup_logging


@pytest.fixture
def today(monkeypatch):
    current = {"day": date(2026, 10, 5)}
    monkeypatch.setattr(log_config, "_today", lambda: current["day"])
    return current


@pytest.fixture
def logger():
    log = logging.getLogger("tests.daily")
    log.propagate = False
    log.setLevel(logging.INFO)
    yield log
    for handler in log.handlers[:]:
        handler.close()
        log.removeHandler(handler)


def test_each_day_goes_to_its_own_file(tmp_path, today, logger):
    logger.addHandler(DailyFileHandler(tmp_path, retention_days=30))

    logger.info("first day")
    today["day"] = date(2026, 10, 6)
    logger.info("second day")
    logger.handlers[0].flush()

    assert (tmp_path / "2026-10-05.log").read_text(encoding="utf-8").strip() == "first day"
    assert (tmp_path / "2026-10-06.log").read_text(encoding="utf-8").strip() == "second day"


def test_old_files_are_removed_on_day_change(tmp_path, today, logger):
    for day in ("2026-10-01", "2026-10-02", "2026-10-03"):
        (tmp_path / f"{day}.log").write_text("old")
    (tmp_path / "notes.log").write_text("not ours")
    logger.addHandler(DailyFileHandler(tmp_path, retention_days=3))  # хранит 03, 04, 05

    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-10-03.log", "2026-10-05.log", "notes.log"]

    today["day"] = date(2026, 10, 6)  # теперь хранит 04, 05, 06
    logger.info("new day")

    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-10-05.log", "2026-10-06.log", "notes.log"]


def test_setup_writes_to_daily_file(tmp_path, today):
    setup_logging("INFO", str(tmp_path / "logs"), retention_days=7)
    try:
        logging.getLogger("tests").info("Daily export completed: 10 messages")
        for handler in logging.getLogger().handlers:
            handler.flush()

        content = (tmp_path / "logs" / "2026-10-05.log").read_text(encoding="utf-8")
        assert "Daily export completed: 10 messages" in content
    finally:
        for handler in logging.getLogger().handlers[:]:
            handler.close()
            logging.getLogger().removeHandler(handler)


def test_console_only_without_log_dir():
    setup_logging("INFO", None, retention_days=7)
    try:
        assert [type(h) for h in logging.getLogger().handlers] == [logging.StreamHandler]
    finally:
        for handler in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(handler)
