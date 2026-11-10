import logging
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.security.replay import BANK_TIMEZONE
from app.service_logging import DailyFileHandler, cleanup_old_logs


class ServiceLogTests(unittest.TestCase):
    def test_crosses_beijing_midnight_without_restarting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handler = DailyFileHandler(root)
            handler.setFormatter(logging.Formatter("%(message)s"))
            try:
                for instant, message in ((datetime(2026, 11, 2, 15, 59, tzinfo=timezone.utc), "yesterday"),
                                         (datetime(2026, 11, 2, 16, 0, tzinfo=timezone.utc), "today")):
                    record = logging.LogRecord("test", logging.INFO, "", 0, message, (), None)
                    record.created = instant.timestamp()
                    handler.handle(record)
            finally:
                handler.close()
            self.assertEqual((root / "service_20261102.log").read_text(), "yesterday\n")
            self.assertEqual((root / "service_20261103.log").read_text(), "today\n")
            self.assertEqual(len(list(root.iterdir())), 2)

    def test_cleanup_only_expired_date_logs_and_preserves_week_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ["service_20261026.log", "service_20261027.log", "service_20261103.log",
                     "service_20261399.log", "service.log", "service_20261026.log.1", "orders.sqlite3"]
            for name in names:
                (root / name).write_text("keep")
            with patch("app.service_logging.logging.getLogger"):
                self.assertTrue(cleanup_old_logs(root, datetime(2026, 11, 3, 1, tzinfo=BANK_TIMEZONE)))
            self.assertFalse((root / names[0]).exists())
            self.assertTrue(all((root / name).read_text() == "keep" for name in names[1:]))

    def test_cleanup_failure_is_logged_and_can_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "service_20261020.log"
            file.write_text("keep")
            now = datetime(2026, 11, 3, 1, tzinfo=BANK_TIMEZONE)
            with patch("app.service_logging.logging.getLogger") as logger:
                with patch.object(Path, "unlink", side_effect=PermissionError("file in use")):
                    self.assertFalse(cleanup_old_logs(root, now))
                logger.return_value.exception.assert_called_once()
                self.assertTrue(cleanup_old_logs(root, now))
            self.assertFalse(file.exists())

    def test_scan_cleanup_schedule_and_failure_retry(self):
        from app.workers.order_scan import OrderScanner
        with tempfile.TemporaryDirectory() as tmp:
            scanner = OrderScanner(Path(tmp) / "data")
            scanner.initialize()
            now = datetime(2026, 11, 3, 0, tzinfo=BANK_TIMEZONE)
            with patch("app.workers.order_scan.cleanup_old_logs", return_value=False) as cleanup:
                scanner.scan(now)
                cleanup.assert_not_called()
                scanner.scan(now.replace(hour=1))
                self.assertEqual(cleanup.call_count, 1)
                cleanup.return_value = True
                scanner.scan(now.replace(hour=1, minute=1))
                scanner.scan(now.replace(hour=2))
                self.assertEqual(cleanup.call_count, 2)
                scanner.scan(now.replace(day=4, hour=1))
                self.assertEqual(cleanup.call_count, 3)
