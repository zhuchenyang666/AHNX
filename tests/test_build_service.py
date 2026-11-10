from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import build_service


class BuildConfigTests(unittest.TestCase):
    def test_build_preserves_selected_environment(self):
        for active, with_data in (("local", True), ("production", False)):
            with self.subTest(active=active), tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
                root = Path(tmp)
                resources = root/"resources"
                resources.mkdir()
                content = f'# Keep this configuration unchanged\nserver:\n  active: {active}\n  sftppath: "./安徽农信借记卡订单文件"\n  scan-interval-ms: 3600000\n'
                (resources/"application.yaml").write_text(content, encoding="utf-8")
                (resources/"orders.sqlite3").write_bytes(b"private order records")
                (resources/"replay.sqlite3").write_bytes(b"runtime sequences")
                if with_data:
                    (root/"安徽农信借记卡订单文件"/"data").mkdir(parents=True)
                    (root/"安徽农信借记卡订单文件"/"report").mkdir()
                    report = root/"安徽农信借记卡订单文件"/"report"
                    (report/"orders.sqlite3").write_bytes(b"finished report orders")
                def create_executable(command, **kwargs):
                    self.assertIn("--onefile", command)
                    output = Path(command[command.index("--distpath") + 1])
                    output.mkdir(parents=True, exist_ok=True)
                    name = command[command.index("--name") + 1]
                    (output / f"{name}.exe").write_bytes(b"test executable")

                with patch.object(build_service, "ROOT", root), patch("build_service.subprocess.run", side_effect=create_executable):
                    build_service.build()
                with zipfile.ZipFile(root/"dist"/"AHNX-Service-Windows-x64.zip") as archive:
                    self.assertEqual({item.filename for item in archive.infolist() if not item.is_dir()}, {
                        "AHNX-Service/AHNX-Service.exe", "AHNX-Service/AHNX-TestClient.exe",
                        "AHNX-Service/resources/application.yaml", "AHNX-Service/使用说明.txt",
                    })
                    self.assertEqual(archive.read("AHNX-Service/resources/application.yaml"),(resources/"application.yaml").read_bytes())
