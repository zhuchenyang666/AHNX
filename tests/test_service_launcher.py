import logging
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import service_launcher


class LauncherTests(unittest.TestCase):
    def test_start_notification_and_cleanup(self):
        notified = threading.Event()
        class FakeServer:
            def __init__(self, config):
                self.started = False
            async def startup(self, sockets=None):
                self.started = True
            def run(self):
                coro = self.startup()
                try:
                    coro.send(None)
                except StopIteration:
                    pass
                finally:
                    coro.close()
                assert notified.wait(2)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            resources = Path(tmp)/"resources"
            resources.mkdir()
            (resources/"replay.sqlite3").write_bytes(b"test")
            with patch.object(service_launcher, "APP_DIRECTORY", Path(tmp)), \
                 patch("uvicorn.Server", FakeServer), \
                 patch.object(service_launcher, "notify", side_effect=lambda *a, **k: notified.set()) as notify:
                self.assertEqual(service_launcher.start_service(), 0)
                self.assertIn("started successfully", notify.call_args.args[0])
            self.assertFalse((resources/"replay.sqlite3").exists())
            log = next(resources.glob("service_????????.log")).read_text(encoding="utf-8")
            self.assertRegex(log, r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \d{3} INFO root: Service stopped")

    def test_start_failure_notification(self):
        class BrokenServer:
            def __init__(self, config):
                self.started = False
            def run(self):
                raise SystemExit(1)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            with patch.object(service_launcher, "APP_DIRECTORY", Path(tmp)), \
                 patch("uvicorn.Server", BrokenServer), \
                 patch.object(service_launcher, "notify") as notify:
                self.assertEqual(service_launcher.start_service(), 1)
                self.assertIn("failed to start", notify.call_args.args[0])
                self.assertTrue(notify.call_args.kwargs["error"])
