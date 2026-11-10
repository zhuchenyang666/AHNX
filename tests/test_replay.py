import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.security.replay import BANK_TIMEZONE, validate_and_claim
from app.services import CardProgressLogisticsQueryServiceImpl
from tests.test_card_progress_logistics_query import make_request


class ReplayTests(unittest.TestCase):
    def test_window_duplicate_and_persistence(self):
        now = datetime(2026, 10, 30, 0, 1, tzinfo=BANK_TIMEZONE)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            db = Path(tmp)/"replay.sqlite3"
            for offset in (-301, 301):
                requested = now + timedelta(seconds=offset)
                header = SimpleNamespace(rqstDate=requested.strftime("%Y-%m-%d"), rqstTime=requested.strftime("%H:%M:%S.%f")[:12], globalSq=str(offset))
                with self.assertRaisesRegex(ValueError, "5 minutes"):
                    validate_and_claim(header, db, now)
            for offset in (-300, 0, 300):
                requested = now + timedelta(seconds=offset)
                header = SimpleNamespace(rqstDate=requested.strftime("%Y-%m-%d"), rqstTime=requested.strftime("%H:%M:%S.%f")[:12], globalSq=str(offset))
                validate_and_claim(header, db, now)
                with self.assertRaisesRegex(ValueError, "repeat"):
                    validate_and_claim(header, db, now)

    def test_concurrent_claim_and_empty_body_replay(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            db = Path(tmp)/"replay.sqlite3"
            header = make_request({}).transaction.header.sysHeader
            def claim(_):
                try:
                    validate_and_claim(header, db)
                    return True
                except ValueError:
                    return False
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(sum(pool.map(claim, range(4))), 1)
            request = make_request({})
            def run():
                coro = CardProgressLogisticsQueryServiceImpl().execute(request)
                try:
                    coro.send(None)
                except StopIteration as result:
                    return result.value.transaction.header.sysHeader
                finally:
                    coro.close()
            with patch("app.services.esb.validate_and_claim", side_effect=lambda header: validate_and_claim(header, db)):
                self.assertEqual(run().bizResCd, "AAAAAAA")
                self.assertIn("repeat", run().bizResText)
