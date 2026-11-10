"""按北京时间日期写日志，并清理超过七天的日期日志。"""
import logging
import re
from datetime import datetime, timedelta

from app.security.replay import BANK_TIMEZONE


class DailyFileHandler(logging.FileHandler):
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        super().__init__(self.path_for(datetime.now(BANK_TIMEZONE).date()), encoding="utf-8", delay=True)

    def path_for(self, day):
        return self.directory / f"service_{day:%Y%m%d}.log"

    def emit(self, record):
        try:
            path = str(self.path_for(datetime.fromtimestamp(record.created, BANK_TIMEZONE).date()).resolve())
            if path != self.baseFilename:
                if self.stream:
                    self.stream.close()
                self.stream = None
                self.baseFilename = path
            super().emit(record)
        except Exception:
            self.handleError(record)


def cleanup_old_logs(directory, now):
    logger = logging.getLogger(__name__)
    logger.info("Checking expired service logs")
    complete = True
    for file in directory.glob("service_*.log"):
        match = re.fullmatch(r"service_([0-9]{8})\.log", file.name)
        if not match or not file.is_file():
            continue
        try:
            day = datetime.strptime(match[1], "%Y%m%d").date()
        except ValueError:
            continue
        if day < now.date() - timedelta(days=7):
            try:
                file.unlink()
                logger.info("Removed expired service log: %s", file.name)
            except OSError:
                complete = False
                logger.exception("Cannot remove expired service log: %s; will retry", file.name)
    return complete
