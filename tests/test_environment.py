import os
import re
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
from app.core.config import CONFIG_FILE, load_application_yaml


class EnvironmentTests(unittest.TestCase):
    def test_exe_uses_yaml_and_source_allows_override(self):
        data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
        data["server"]["active"] = "local"
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            config = Path(tmp)/"application.yaml"
            config.write_text(yaml.safe_dump(data), encoding="utf-8")
            with patch("app.core.config.CONFIG_FILE", config), patch.dict(os.environ, {"AHNX_ENV":"production"}):
                with patch.object(sys, "frozen", True, create=True):
                    self.assertEqual(load_application_yaml().active, "local")
                    self.assertEqual(load_application_yaml().environment.port, 8000)
                with patch.object(sys, "frozen", False, create=True):
                    self.assertEqual(load_application_yaml().active, "production")

    def test_sftp_root_path_resolves_from_program_directory(self):
        from app.core.config import server_config
        from app.paths import APP_DIRECTORY
        config = server_config.model_copy(update={"sftppath": "."})
        self.assertEqual(config.order_data_directory, APP_DIRECTORY / "data")
        with tempfile.TemporaryDirectory() as tmp:
            config = server_config.model_copy(update={"sftppath": tmp})
            self.assertEqual(config.order_data_directory, Path(tmp).resolve() / "data")

    def test_scan_interval_default_override_and_validation(self):
        from pydantic import ValidationError
        from app.core.config import ServerConfig, server_config
        data = server_config.model_dump(by_alias=True)
        data.pop("scan-interval-ms")
        self.assertEqual(ServerConfig.model_validate(data).scan_interval_ms, 3600000)
        data["scan-interval-ms"] = 60000
        self.assertEqual(ServerConfig.model_validate(data).scan_interval_ms, 60000)
        for value in (0, -1, 1.5, "60000", True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ServerConfig.model_validate(dict(data, **{"scan-interval-ms": value}))

    def test_windows_sftp_path_quoting(self):
        template = CONFIG_FILE.read_text(encoding="utf-8")
        cases = [
            (r'"D:\data"', r'D:\data'),
            (r'"D:\\data"', r'D:\data'),
            (r'"D:\temp\new\reports"', r'D:\temp\new\reports'),
            (r'"D:\Users\农信订单" # local folder', r'D:\Users\农信订单'),
            (r'"D:\"', 'D:' + chr(92)),
            (r"'D:\data'", r'D:\data'),
            (r'D:\data', r'D:\data'),
            ('"D:/data"', 'D:/data'),
            ('"."', '.'),
            (r'".\安徽农信借记卡订单文件"', r'.\安徽农信借记卡订单文件'),
            (r'".\\安徽农信借记卡订单文件"', r'.\安徽农信借记卡订单文件'),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "application.yaml"
            for raw, expected in cases:
                with self.subTest(raw=raw):
                    config.write_text(re.sub(r"(?m)^  sftppath:.*$", lambda _: "  sftppath: " + raw, template), encoding="utf-8")
                    with patch("app.core.config.CONFIG_FILE", config):
                        self.assertEqual(load_application_yaml().sftppath, expected)

    def test_other_yaml_strings_keep_escape_rules(self):
        template = CONFIG_FILE.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "application.yaml"
            config.write_text(template.replace('title: 安徽农信银行卡商接口', r'title: "line\nnext"'), encoding="utf-8")
            with patch("app.core.config.CONFIG_FILE", config):
                self.assertEqual(load_application_yaml().title, "line\nnext")
