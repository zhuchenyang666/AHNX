"""逐行全量读取状态文件，同一订单更新到 report 单库。"""
import asyncio
import logging
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import ValidationError

from app.core.config import server_config
from app.models import CardOrderFileRequest, CardOrderFileTransBizBody
from app.repositories.orders import ORDER_DATA_DIRECTORY, order_progress
from app.security.replay import BANK_TIMEZONE
from app.paths import APP_DIRECTORY
from app.service_logging import cleanup_old_logs

logger = logging.getLogger(__name__)
ORDER_FIELDS = tuple(name for name in CardOrderFileTransBizBody.model_fields
                     if name not in ("logisticscompany", "logisticsno"))


class OrderScanner:
    def __init__(self, directory: Path = ORDER_DATA_DIRECTORY, database: Path | None = None):
        self.directory = directory
        self.report_directory = directory.parent / "report"
        self.database = database or self.report_directory / "orders.sqlite3"
        self.started = False
        self.last_log_cleanup = None

    def initialize(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.report_directory.mkdir(parents=True, exist_ok=True)
        fields = [f'"{name}" {"INTEGER" if name == "cardNum" else "TEXT"}'
                  + (" PRIMARY KEY" if name == "orderId" else "") for name in ORDER_FIELDS]
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS orders (" + ",".join(fields) + """,
                crdprdsts TEXT NOT NULL CHECK(crdprdsts IN ('pending','making','finished')),
                logisticscompany TEXT, logisticsno TEXT,
                CHECK ((crdprdsts = 'finished' AND logisticscompany IS NOT NULL
                        AND length(trim(logisticscompany)) > 0 AND logisticsno IS NOT NULL
                        AND length(trim(logisticsno)) > 0)
                    OR (crdprdsts != 'finished' AND logisticscompany IS NULL AND logisticsno IS NULL))
            )""")
            db.execute("CREATE TABLE IF NOT EXISTS scans (day TEXT PRIMARY KEY)")

    def scan_day(self, day, now):
        complete = True
        columns = list(ORDER_FIELDS) + ["crdprdsts", "logisticscompany", "logisticsno"]
        names = ",".join('"' + name + '"' for name in columns)
        updates = ",".join('"' + name + '"=excluded."' + name + '"' for name in columns if name != "orderId")
        rank = "CASE {}.crdprdsts WHEN 'pending' THEN 0 WHEN 'making' THEN 1 ELSE 2 END"
        sql = (f"INSERT INTO orders ({names}) VALUES ({','.join('?' for _ in columns)}) "
               f"ON CONFLICT(orderId) DO UPDATE SET {updates} WHERE {rank.format('orders')} <= {rank.format('excluded')}")
        with closing(sqlite3.connect(self.database)) as db, db:
            for file in sorted((self.directory / day.strftime("%Y%m%d")).glob("*.txt")):
                match = re.fullmatch(r"(pending|making|finished|finshed)_[0-9]{8}\.txt", file.name)
                if not match:
                    logger.warning("Skipping invalid status filename: %s", file)
                    continue
                status = "finished" if match[1] == "finshed" else match[1]
                try:
                    before = file.stat()
                    text = file.read_text(encoding="utf-8-sig")
                    after = file.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        complete = False
                        continue
                except (OSError, UnicodeError):
                    complete = False
                    logger.exception("Cannot read status file; will retry: %s", file)
                    continue
                for line_number, line in enumerate(text.splitlines(), 1):
                    if not line.strip():
                        continue
                    try:
                        order = CardOrderFileRequest.from_json(line).biz
                        company = order.logisticscompany if status == "finished" else None
                        number = order.logisticsno if status == "finished" else None
                        if status == "finished" and not (company and number):
                            raise ValueError("物流字段为空错误：finished 的 logisticscompany、logisticsno 必须存在且非空")
                        order_progress(order, status, company, number)
                        values = order.to_dict()
                        db.execute(sql, [values[name] for name in ORDER_FIELDS] + [status, company, number])
                    except ValueError as exc:
                        complete = False
                        reason = ("; ".join(".".join(str(part) for part in error["loc"]) + ": " + error["msg"]
                                            for error in exc.errors()) if isinstance(exc, ValidationError) else str(exc))
                        logger.error("%s 第 %s 行数据校验错误：%s；跳过该行，下轮重试",
                                     file, line_number, reason)
            if complete and (day < now.date() - timedelta(days=1) or (day < now.date() and now.hour >= 1)):
                db.execute("INSERT OR IGNORE INTO scans VALUES (?)", (day.isoformat(),))
        return complete

    def scan(self, now=None):
        now = now or datetime.now(BANK_TIMEZONE)
        if not self.directory.is_dir():
            raise FileNotFoundError(f"Order data directory does not exist: {self.directory}")
        today = now.date()
        if now.hour >= 1 and self.last_log_cleanup != today:
            if cleanup_old_logs(APP_DIRECTORY / "resources", now):
                self.last_log_cleanup = today
        with closing(sqlite3.connect(self.database)) as db:
            last = db.execute("SELECT MAX(day) FROM scans").fetchone()[0]
        # 正常只补扫昨天；停机跨日后，从最后一次完成的日期继续补扫。
        day = datetime.strptime(last, "%Y-%m-%d").date() + timedelta(days=1) if last else today - timedelta(days=1)
        while day < today:
            if day == today - timedelta(days=1) and now.hour < 1 and self.started:
                break
            if not self.scan_day(day, now):
                break
            day += timedelta(days=1)
        self.scan_day(today, now)
        self.started = True

    def load_records(self):
        with closing(sqlite3.connect(self.database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM orders").fetchall()
        return [order_progress(
            CardOrderFileTransBizBody.from_dict({name: row[name] for name in ORDER_FIELDS}),
            row["crdprdsts"], row["logisticscompany"], row["logisticsno"],
        ) for row in rows]

    async def run(self, stop):
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=server_config.scan_interval_ms / 1000)
                return
            except TimeoutError:
                pass
            try:
                await asyncio.to_thread(self.scan)
            except Exception:
                logger.exception("Order scan failed; will retry next interval")


order_scanner = OrderScanner()
