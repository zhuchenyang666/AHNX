"""持久化全局流水号，避免并发请求和服务重启绕过去重。"""
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from app.paths import APP_DIRECTORY

REPLAY_DATABASE = APP_DIRECTORY / "resources" / "replay.sqlite3"
BANK_TIMEZONE = timezone(timedelta(hours=8))


def validate_and_claim(header, database=REPLAY_DATABASE, now=None):
    now = now or datetime.now(BANK_TIMEZONE)
    requested = datetime.strptime(f"{header.rqstDate} {header.rqstTime}", "%Y-%m-%d %H:%M:%S.%f").replace(
        tzinfo=BANK_TIMEZONE)
    if abs((now - requested).total_seconds()) > 300:
        raise ValueError("Request timestamp must be within 5 minutes of server time; generate a new request")
    with closing(sqlite3.connect(database, timeout=5)) as connection, connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS request_sequences (global_sq TEXT PRIMARY KEY, received_at TEXT NOT NULL)")
        try:
            connection.execute("INSERT INTO request_sequences VALUES (?, ?)", (header.globalSq, now.isoformat()))
        except sqlite3.IntegrityError as exc:
            raise ValueError("globalSq repeat error") from exc
