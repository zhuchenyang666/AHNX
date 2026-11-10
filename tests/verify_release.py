"""发布包集成验证：独立临时副本启动、查询、重复启动、停止。"""
import json
import os
from pathlib import Path
from zipfile import ZipFile
import socket
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
from uuid import uuid4
from datetime import datetime, timezone, timedelta
import yaml

ROOT = Path(__file__).resolve().parents[1]


def verify():
    with tempfile.TemporaryDirectory(prefix="release-check-", dir=ROOT / "build") as tmp:
        target = Path(tmp) / "AHNX-Service"
        with ZipFile(ROOT / "dist" / "AHNX-Service-Windows-x64.zip") as archive:
            assert {name for name in archive.namelist() if name.endswith(".exe")} == {
                "AHNX-Service/AHNX-Service.exe", "AHNX-Service/AHNX-TestClient.exe"}
            assert all("_internal/" not in name and "安徽农信借记卡订单文件/" not in name for name in archive.namelist())
            archive.extractall(tmp)
        config_file = target / "resources" / "application.yaml"
        config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        assert config["server"]["scan-interval-ms"] == yaml.safe_load((ROOT / "resources" / "application.yaml").read_text(encoding="utf-8"))["server"]["scan-interval-ms"]
        config["server"]["scan-interval-ms"] = 100  # 仅临时副本加速验证定时扫描。
        config["server"]["active"] = "production"
        config["server"]["environments"]["production"].update({"port":port, "listen-host":"127.0.0.1"})
        config["server"]["sftppath"] = "./安徽农信借记卡订单文件"
        config_file.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        fixture = ROOT / "tests" / "fixtures" / "finished_20260914.txt"
        today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")
        folder = target / "安徽农信借记卡订单文件" / "data" / today
        folder.mkdir(parents=True, exist_ok=True)
        order_file = folder / fixture.name
        order_file.write_bytes(fixture.read_bytes())
        os.utime(order_file, (time.time() - 120, time.time() - 120))
        environment = dict(os.environ, AHNX_ENV="production")
        process = subprocess.Popen([str(target / "AHNX-Service.exe"), "--silent"], cwd=ROOT,
            env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            base = f"http://127.0.0.1:{port}"
            for attempt in range(30):
                if process.poll() is not None:
                    raise RuntimeError(f"EXE exited: {process.returncode}; " + (target / "resources" / f"service_{datetime.now(timezone(timedelta(hours=8))):%Y%m%d}.log").read_text(encoding="utf-8"))
                try:
                    with urlopen(base+"/", timeout=1) as response:
                        assert json.load(response)["version"] == "1.7.0"
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise RuntimeError("EXE startup timed out")
            now = datetime.now()
            payload = {"Transaction":{"Header":{"sysHeader":{
                "servCd":"3033000313", "globalSq":"029"+uuid4().hex[:26],
                "rqstDate":now.strftime("%Y-%m-%d"), "rqstTime":now.strftime("%H:%M:%S.%f")[:12],
                "rqstSysCd":"029", "prvdSysCd":"662", "tranCode":"ICCARD12001001"}},
                "Body":{"request":{"bizBody":{"page":1,"limit":10}}}}}
            with urlopen(Request(base+"/ICCARD12001001", data=json.dumps(payload).encode(),
                                 headers={"Content-Type":"application/json"}), timeout=5) as response:
                result = json.load(response)
            assert (target / "安徽农信借记卡订单文件" / "report").is_dir()
            assert result["Transaction"]["Header"]["sysHeader"]["bizResCd"] == "AAAAAAA", result
            assert result["Transaction"]["Body"]["response"]["bizBody"]["count"] >= 1, result
            finished = [record for record in result["Transaction"]["Body"]["response"]["bizBody"]["records"]
                        if record["crdprdsts"] == "finished"]
            assert finished and all(record["logisticscompany"] and record["logisticsno"] for record in finished)
            feedback_payload = json.loads(json.dumps(payload))
            feedback_payload["Transaction"]["Header"]["sysHeader"].update(
                tranCode="ICCARD12001002", servCd="3033000314", globalSq="029" + uuid4().hex[:26])
            with urlopen(Request(base+"/ICCARD12001002", data=json.dumps(feedback_payload).encode(),
                                 headers={"Content-Type":"application/json"}), timeout=5) as response:
                feedback_result = json.load(response)
            assert feedback_result["Transaction"]["Body"]["response"]["bizBody"]["count"] == 0
            from urllib.error import HTTPError
            try:
                urlopen(base+"/missing", timeout=5)
                raise AssertionError("Missing URL should fail")
            except HTTPError as response:
                assert response.code == 404
                assert json.load(response) == {"code": 404, "msg": "url not found"}
            # 启动后新增一份唯一文件，等待轮询导入，验证配置实际被使用。
            import sqlite3
            from contextlib import closing
            timer_order = json.loads(next(line for line in fixture.read_text(encoding="utf-8-sig").splitlines() if line.strip()))
            timer_order["biz"]["orderId"] = "TIMER-" + timer_order["biz"]["orderId"]
            added = folder / "making_20991231.txt"
            added.write_text(json.dumps(timer_order), encoding="utf-8")
            os.utime(added, (time.time() - 120, time.time() - 120))
            for attempt in range(30):
                with closing(sqlite3.connect(target / "安徽农信借记卡订单文件" / "report" / "orders.sqlite3")) as db:
                    imported = db.execute("SELECT COUNT(*) FROM orders WHERE orderId = ?", (timer_order["biz"]["orderId"],)).fetchone()[0]
                if imported:
                    break
                time.sleep(0.1)
            assert imported == 1, "Configured scan timer did not import the new file"
            with closing(sqlite3.connect(target / "安徽农信借记卡订单文件" / "report" / "orders.sqlite3")) as db:
                state = db.execute("SELECT crdprdsts, logisticscompany, logisticsno FROM orders WHERE orderId = ?", (timer_order["biz"]["orderId"],)).fetchone()
            assert state == ("making", None, None), state
            # 在同名文件追加第二行订单，验证 EXE 不会按已读文件名跳过。
            timer_order["biz"]["orderId"] += "-2"
            with added.open("a", encoding="utf-8") as file:
                file.write("\n\n" + json.dumps(timer_order) + "\n\n")
            for attempt in range(30):
                with closing(sqlite3.connect(target / "安徽农信借记卡订单文件" / "report" / "orders.sqlite3")) as db:
                    appended = db.execute("SELECT COUNT(*) FROM orders WHERE orderId = ?", (timer_order["biz"]["orderId"],)).fetchone()[0]
                if appended:
                    break
                time.sleep(0.1)
            assert appended == 1, "Same filename append was not imported"
            payload["Transaction"]["Header"]["sysHeader"]["globalSq"] = "029" + uuid4().hex[:26]
            with urlopen(Request(base+"/ICCARD12001001", data=json.dumps(payload).encode(),
                                 headers={"Content-Type":"application/json"}), timeout=5) as response:
                current = json.load(response)
            assert any(row["orderid"] == timer_order["biz"]["orderId"] for row in current["Transaction"]["Body"]["response"]["bizBody"]["records"])
            assert len(list((target / "安徽农信借记卡订单文件" / "report").rglob("*.sqlite3"))) == 1
            invalid = json.loads(json.dumps(timer_order))
            invalid["biz"]["orderId"] = "INVALID-LOGISTICS"
            invalid["biz"]["logisticscompany"] = ""
            invalid["biz"]["logisticsno"] = None
            bad = folder / "finished_20991231.txt"
            bad.write_text(json.dumps(invalid), encoding="utf-8")
            for attempt in range(30):
                log = (target / "resources" / f"service_{datetime.now(timezone(timedelta(hours=8))):%Y%m%d}.log").read_text(encoding="utf-8")
                if bad.name in log and "物流字段为空错误" in log:
                    break
                time.sleep(0.1)
            assert bad.name in log and "物流字段为空错误" in log, log
            with closing(sqlite3.connect(target / "安徽农信借记卡订单文件" / "report" / "orders.sqlite3")) as db:
                assert db.execute("SELECT COUNT(*) FROM orders WHERE orderId='INVALID-LOGISTICS'").fetchone()[0] == 0
            duplicate = subprocess.run([str(target / "AHNX-Service.exe"), "--silent"], env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            assert duplicate.returncode == 1
            stopped = subprocess.run([str(target / "AHNX-Service.exe"), "--stop", "--silent"], env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=25)
            assert stopped.returncode == 0, stopped.returncode
            assert process.wait(timeout=10) == 0
            log_file = target / "resources" / f"service_{datetime.now(timezone(timedelta(hours=8))):%Y%m%d}.log"
            assert log_file.is_file()
            import re
            log_text = log_file.read_text(encoding="utf-8")
            assert "Service started successfully" in log_text
            assert all(re.match(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \d{3} (INFO|WARNING|ERROR)", line) for line in log_text.splitlines() if line)
            assert (target / "安徽农信借记卡订单文件" / "report" / "orders.sqlite3").is_file()
            assert not (target / "resources" / "replay.sqlite3").exists()
            assert not list((target / "resources").glob("replay.sqlite3-*"))
            assert not (target / "_internal").exists()
            config["server"]["active"] = "local"
            config["server"]["environments"]["local"].update({"port":port, "listen-host":"127.0.0.1"})
            config_file.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
            # 故意保留 AHNX_ENV=production，验证外部 YAML local 仍被采用。
            process = subprocess.Popen([str(target / "AHNX-Service.exe"), "--silent"], cwd=ROOT,
                env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
            for attempt in range(30):
                if process.poll() is not None:
                    raise RuntimeError("Local EXE exited unexpectedly")
                try:
                    with urlopen(base+"/", timeout=1) as response:
                        assert json.load(response)["version"] == "1.7.0"
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise RuntimeError("Local EXE startup timed out")
            assert "active=local" in log_file.read_text(encoding="utf-8")
            stopped = subprocess.run([str(target / "AHNX-Service.exe"), "--stop", "--silent"], env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=25)
            assert stopped.returncode == 0
            assert process.wait(timeout=10) == 0
            print("PASS: production and YAML-local startup, external resources, query, duplicate protection, log format, replay cleanup and graceful shutdown.")
        finally:
            if process.poll() is None:
                subprocess.run([str(target / "AHNX-Service.exe"), "--stop", "--silent"], env=environment,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=25)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == "__main__":
    verify()
