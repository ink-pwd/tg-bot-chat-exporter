import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class DailyFileHandler(logging.FileHandler):
    """Каждый день — свой файл: logs/2026-10-05.log, logs/2026-10-06.log, …

    Дата считается по UTC, как и время в строках лога. Файлы старше
    retention_days удаляются при переходе на новый день и при старте.
    """

    def __init__(self, directory: Path, retention_days: int) -> None:
        self._directory = directory
        self._retention_days = retention_days
        self._day = _today()
        directory.mkdir(parents=True, exist_ok=True)
        super().__init__(self._path(self._day), encoding="utf-8")
        self._remove_expired()

    def emit(self, record: logging.LogRecord) -> None:
        day = _today()
        if day != self._day:
            self._switch_to(day)
        super().emit(record)

    def _switch_to(self, day: date) -> None:
        self.acquire()
        try:
            if self.stream is not None:
                self.stream.close()
                self.stream = None
            self._day = day
            self.baseFilename = str(self._path(day))
        finally:
            self.release()
        self._remove_expired()

    def _path(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}.log"

    def _remove_expired(self) -> None:
        oldest_kept = self._day - timedelta(days=self._retention_days - 1)
        for file in self._directory.glob("*.log"):
            try:
                file_day = date.fromisoformat(file.stem)
            except ValueError:
                continue  # не наш файл
            if file_day < oldest_kept:
                file.unlink(missing_ok=True)


def setup_logging(level: str, log_dir: str | None, retention_days: int) -> None:
    """Логи в консоль и, если задан log_dir, в отдельный файл на каждый день."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_dir:
        handlers.append(DailyFileHandler(Path(log_dir), retention_days))
    logging.basicConfig(level=level, format=_FORMAT, handlers=handlers, force=True)
    # Telethon и pymorphy3 на INFO пишут служебные подробности — нам они не нужны
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("pymorphy3").setLevel(logging.WARNING)


def _today() -> date:
    return datetime.now(timezone.utc).date()
