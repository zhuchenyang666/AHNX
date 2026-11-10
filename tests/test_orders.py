import asyncio
import json
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
import sqlite3

from app.security.replay import BANK_TIMEZONE
from app.workers.order_scan import OrderScanner


class OrderFileTests(unittest.TestCase):
    def setUp(self):
        cleaner = patch("app.workers.order_scan.cleanup_old_logs", return_value=True)
        self.cleaner = cleaner.start()
        self.addCleanup(cleaner.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data"
        self.scanner = OrderScanner(self.data)
        self.scanner.initialize()
        self.now = datetime(2026, 11, 3, 12, tzinfo=BANK_TIMEZONE)
        source = Path(__file__).parent / "fixtures" / "finished_20260914.txt"
        self.order = json.loads(next(line for line in source.read_text(encoding="utf-8-sig").splitlines() if line.strip()))

    def order_json(self, order_id):
        order = json.loads(json.dumps(self.order))
        order["biz"]["orderId"] = order_id
        order["biz"].pop("logisticscompany", None)
        order["biz"].pop("logisticsno", None)
        return json.dumps(order)

    def finished_json(self, order_id):
        order = json.loads(self.order_json(order_id))
        order["biz"].update(logisticscompany="顺丰速运", logisticsno="SF5149695523766")
        return json.dumps(order)

    def write(self, day="20261103", name="making_20261103.txt", lines=None):
        folder = self.data / day
        folder.mkdir(parents=True, exist_ok=True)
        file = folder / name
        if lines is None:
            order = json.loads(self.order_json("001"))
            if name.startswith(("finished_", "finshed_")):
                order["biz"].update(logisticscompany="顺丰速运", logisticsno="SF5149695523766")
            lines = [json.dumps(order)]
        file.write_text("\n\n  \n" + "\n\n".join(lines) + "\n\n", encoding="utf-8-sig")
        return file

    def test_multiline_and_same_filename_append_are_fully_reread(self):
        file = self.write(lines=[self.order_json("001"), self.order_json("002")])
        before = file.read_bytes(), file.stat().st_mtime_ns
        self.scanner.scan(self.now)
        self.assertEqual(len(self.scanner.load_records()), 2)
        self.assertEqual((file.read_bytes(), file.stat().st_mtime_ns), before)
        self.write(lines=[self.order_json("001"), self.order_json("002"), self.order_json("003")])
        self.scanner.scan(self.now)
        self.assertEqual(len(self.scanner.load_records()), 3)
        self.assertEqual(len(list(self.scanner.report_directory.glob("*.sqlite3"))), 1)
        self.assertFalse(any(p.is_dir() for p in self.scanner.report_directory.iterdir()))

    def test_status_updates_do_not_regress_and_primary_key_is_order_id(self):
        self.write(name="pending_20261105.txt")
        self.scanner.scan(self.now)
        self.assertEqual(self.scanner.load_records()[0].crdPrdSts, "pending")
        self.write()
        self.scanner.scan(self.now)
        self.assertEqual(self.scanner.load_records()[0].crdPrdSts, "making")
        self.write(name="finished_20261104.txt")
        self.scanner.scan(self.now)
        self.scanner.scan(self.now)
        rows = self.scanner.load_records()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].crdPrdSts, "finished")
        self.assertEqual(rows[0].logisticsCompany, "顺丰速运")
        self.assertEqual(rows[0].logisticsNo, "SF5149695523766")
        restarted = OrderScanner(self.data)
        restarted.initialize()
        restarted.scan(self.now)
        self.assertEqual(restarted.load_records()[0].crdPrdSts, "finished")

    def test_all_original_fields_are_stored_and_reread_updates_values(self):
        self.write()
        self.scanner.scan(self.now)
        updated = json.loads(self.order_json("001"))
        updated["biz"]["address"] = "新地址"
        updated["biz"]["cardFileName"] = "new-file"
        self.write(lines=[json.dumps(updated)])
        self.scanner.scan(self.now)
        with closing(sqlite3.connect(self.scanner.database)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM orders WHERE orderId='001'").fetchone()
            for key, value in updated["biz"].items():
                self.assertEqual(row[key], value)
            self.assertEqual(row["crdprdsts"], "making")
            self.assertIsNone(row["logisticscompany"])
            self.assertIsNone(row["logisticsno"])
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE orders SET crdprdsts='finished'")

    def test_invalid_line_does_not_drop_other_lines_and_retries(self):
        self.write(lines=[self.order_json("001"), "invalid", self.order_json("002")])
        with self.assertLogs("app.workers.order_scan", level="ERROR"):
            self.assertFalse(self.scanner.scan_day(self.now.date(), self.now))
        self.assertEqual(len(self.scanner.load_records()), 2)
        self.write(lines=[self.order_json("001"), self.order_json("002"), self.order_json("003")])
        self.scanner.scan(self.now)
        self.assertEqual(len(self.scanner.load_records()), 3)

    def test_invalid_filename_not_read_and_typo_alias_supported(self):
        self.write(name="unrelated.txt", lines=["invalid"])
        with patch.object(Path, "read_text", side_effect=AssertionError("must not read")):
            with self.assertLogs("app.workers.order_scan", level="WARNING"):
                self.scanner.scan(self.now)
        self.write(name="finshed_20261105.txt")
        with self.assertLogs("app.workers.order_scan", level="WARNING"):
            self.scanner.scan(self.now)
        self.assertEqual(self.scanner.load_records()[0].crdPrdSts, "finished")

    def test_one_am_sweep_and_normal_scan_does_not_read_older_days(self):
        self.write(day="20261101", lines=[self.order_json("older")])
        self.scanner.scan(self.now.replace(hour=0))
        self.write(day="20261102", name="finished_20261104.txt", lines=[self.finished_json("yesterday")])
        self.write(lines=[self.order_json("today")])
        self.scanner.scan(self.now.replace(hour=0, minute=30))
        self.assertEqual([r.orderId for r in self.scanner.load_records()], ["today"])
        self.scanner.scan(self.now.replace(hour=1))
        self.assertEqual({r.orderId for r in self.scanner.load_records()}, {"today", "yesterday"})
        with patch.object(self.scanner, "scan_day", wraps=self.scanner.scan_day) as scan:
            self.scanner.scan(self.now.replace(hour=2))
            self.assertEqual(len(scan.call_args_list), 1)

    def test_downtime_catchup(self):
        self.scanner.scan(self.now)
        self.write(day="20261104", lines=[self.order_json("missed")])
        restarted = OrderScanner(self.data)
        restarted.initialize()
        restarted.scan(self.now.replace(day=5))
        self.assertEqual(restarted.load_records()[0].orderId, "missed")

    def test_startup_and_stop(self):
        from app.app import create_app
        async def start():
            app = create_app()
            async with app.router.lifespan_context(app):
                pass
        with patch("app.app.order_scanner") as scanner:
            scanner.run = AsyncMock()
            asyncio.run(start())
            scanner.initialize.assert_called_once_with()
            scanner.scan.assert_called_once_with()
            scanner.run.assert_awaited_once()
            self.assertTrue(scanner.run.call_args.args[0].is_set())

    def test_timer_retries_and_stops_cleanly(self):
        async def run():
            stop = asyncio.Event()
            def scan():
                if mocked.call_count == 1:
                    raise OSError("temporary failure")
                stop.set()
            with patch.object(self.scanner, "scan", side_effect=scan) as mocked:
                with patch("app.workers.order_scan.server_config.scan_interval_ms", 1):
                    with self.assertLogs("app.workers.order_scan", level="ERROR"):
                        await asyncio.wait_for(self.scanner.run(stop), timeout=2)
            self.assertEqual(mocked.call_count, 2)
        asyncio.run(run())

    def test_finished_missing_or_blank_fields_skip_only_invalid_rows(self):
        lines = []
        for field in ("logisticscompany", "logisticsno"):
            for index, value in enumerate((None, "", "   ", "missing")):
                item = json.loads(self.finished_json(field + str(index)))
                if value == "missing":
                    item["biz"].pop(field)
                else:
                    item["biz"][field] = value
                lines.append(json.dumps(item))
        lines.append(self.finished_json("valid"))
        file = self.write(name="finished_20261104.txt", lines=lines)
        with self.assertLogs("app.workers.order_scan", level="ERROR") as logs:
            self.assertFalse(self.scanner.scan_day(self.now.date(), self.now))
        self.assertEqual(len(logs.output), 8)
        self.assertTrue(all(str(file) in line and "物流字段为空错误" in line for line in logs.output))
        self.assertEqual([r.orderId for r in self.scanner.load_records()], ["valid"])

    def test_nonfinished_accepts_missing_null_and_empty_logistics(self):
        for status in ("pending", "making"):
            lines = []
            for index, value in enumerate((None, "", "   ", "missing")):
                item = json.loads(self.order_json(status + str(index)))
                if value != "missing":
                    item["biz"].update(logisticscompany=value, logisticsno=value)
                lines.append(json.dumps(item))
            self.write(name=status + "_20261103.txt", lines=lines)
        self.scanner.scan(self.now)
        rows = self.scanner.load_records()
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(r.logisticsCompany is None and r.logisticsNo is None for r in rows))

    def test_actual_file_logistics_is_used_and_bad_update_preserves_previous_row(self):
        item = json.loads(self.finished_json("001"))
        item["biz"].update(logisticscompany="中通快递", logisticsno="ZTO123456789")
        self.write(name="finished_20261104.txt", lines=[json.dumps(item)])
        self.scanner.scan(self.now)
        record = self.scanner.load_records()[0]
        self.assertEqual((record.logisticsCompany, record.logisticsNo), ("中通快递", "ZTO123456789"))
        item["biz"]["logisticsno"] = ""
        self.write(name="finished_20261104.txt", lines=[json.dumps(item)])
        with self.assertLogs("app.workers.order_scan", level="ERROR"):
            self.scanner.scan(self.now)
        self.assertEqual(self.scanner.load_records()[0].logisticsNo, "ZTO123456789")

    def test_log_error_is_written_to_service_log(self):
        import logging
        item = json.loads(self.finished_json("001"))
        item["biz"]["logisticsno"] = None
        self.write(name="finished_20261104.txt", lines=[json.dumps(item)])
        file = self.root / "service_20261103.log"
        handler = logging.FileHandler(file, encoding="utf-8")
        logger = logging.getLogger("app.workers.order_scan")
        logger.addHandler(handler)
        try:
            self.scanner.scan(self.now)
        finally:
            logger.removeHandler(handler)
            handler.close()
        text = file.read_text(encoding="utf-8")
        self.assertIn("finished_20261104.txt", text)
        self.assertIn("20261103", text)
        self.assertIn("物流字段为空错误", text)

    def test_cleanup_after_one_am_once_per_day_and_retry_failure(self):
        self.scanner.scan(self.now.replace(hour=0))
        self.cleaner.assert_not_called()
        self.cleaner.return_value = False
        self.scanner.scan(self.now.replace(hour=1))
        self.assertEqual(self.cleaner.call_count, 1)
        self.cleaner.return_value = True
        self.scanner.scan(self.now.replace(hour=1, minute=1))
        self.scanner.scan(self.now.replace(hour=2))
        self.assertEqual(self.cleaner.call_count, 2)
        self.scanner.scan(self.now.replace(day=4, hour=1))
        self.assertEqual(self.cleaner.call_count, 3)
