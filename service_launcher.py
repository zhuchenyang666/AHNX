"""Windows 无终端服务启动/停止入口；StopService.exe 使用同一运行库。"""
import ctypes
from ctypes import wintypes
import hashlib
import logging
from pathlib import Path
import sys
import threading

from app.paths import APP_DIRECTORY
from app.service_logging import DailyFileHandler
from app.security.replay import BANK_TIMEZONE
from datetime import datetime

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
for name, arguments, result in (
    ("CreateMutexW", [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
    ("OpenMutexW", [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
    ("CreateEventW", [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
    ("OpenEventW", [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
    ("SetEvent", [wintypes.HANDLE], wintypes.BOOL),
    ("ResetEvent", [wintypes.HANDLE], wintypes.BOOL),
    ("WaitForSingleObject", [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
    ("ReleaseMutex", [wintypes.HANDLE], wintypes.BOOL),
    ("CloseHandle", [wintypes.HANDLE], wintypes.BOOL),
):
    function = getattr(kernel, name)
    function.argtypes, function.restype = arguments, result

identity = hashlib.sha256(str(APP_DIRECTORY).casefold().encode()).hexdigest()[:24]
MUTEX_NAME = "Local\\AHNX-Mutex-" + identity
EVENT_NAME = "Local\\AHNX-Stop-" + identity


def notify(message, error=False):
    ctypes.windll.user32.MessageBoxW(None, message, "AHNX Service", 0x10 if error else 0x40)


def stop_service(silent=False):
    event = kernel.OpenEventW(0x0002, False, EVENT_NAME)
    if not event:
        if not silent:
            notify("Service is not running.")
        return 1
    mutex = kernel.OpenMutexW(0x00100001, False, MUTEX_NAME)
    try:
        if not kernel.SetEvent(event):
            raise ctypes.WinError(ctypes.get_last_error())
        stopped = mutex and kernel.WaitForSingleObject(mutex, 20000) in (0, 0x80)
        if stopped:
            kernel.ReleaseMutex(mutex)
        if not silent:
            notify("Service stopped." if stopped else "Stop requested; shutdown is still in progress.")
        return 0 if stopped else 2
    finally:
        kernel.CloseHandle(event)
        if mutex:
            kernel.CloseHandle(mutex)


def start_service(silent=False):
    mutex = kernel.CreateMutexW(None, False, MUTEX_NAME)
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = kernel.WaitForSingleObject(mutex, 0) in (0, 0x80)
    if not acquired:
        kernel.CloseHandle(mutex)
        if not silent:
            notify("Service is already running.")
        return 1
    event = None
    watcher = None
    server = None
    try:
        log_directory = APP_DIRECTORY / "resources"
        log_directory.mkdir(exist_ok=True)
        handler = DailyFileHandler(log_directory)
        formatter = logging.Formatter("[%(asctime)s] %(msecs)03d %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        formatter.converter = lambda timestamp: datetime.fromtimestamp(timestamp, BANK_TIMEZONE).timetuple()
        handler.setFormatter(formatter)
        logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
        # windowed EXE 没有 stdout/stderr，避免第三方日志格式器访问空对象。
        for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            logger = logging.getLogger(logger_name)
            logger.handlers.clear()
            logger.propagate = True
        from app.app import create_app
        from app.core import ahnx_server_config
        import uvicorn
        from app.core.config import CONFIG_FILE
        config = ahnx_server_config.environment
        logging.info("Configuration loaded from %s; active=%s", CONFIG_FILE, ahnx_server_config.active)
        event = kernel.CreateEventW(None, True, False, EVENT_NAME)
        if not event:
            raise ctypes.WinError(ctypes.get_last_error())
        kernel.ResetEvent(event)
        class ServiceServer(uvicorn.Server):
            async def startup(self, sockets=None):
                await super().startup(sockets=sockets)
                if self.started:
                    logging.info("Service started successfully")
                    if not silent:
                        # 对话框等待用户确认时，服务仍正常处理请求。
                        threading.Thread(target=notify, args=(f"Service started successfully. Environment: {ahnx_server_config.active}. Port: {config.port}",), daemon=True).start()
        server = ServiceServer(uvicorn.Config(create_app(), host=config.listen_host, port=config.port,
            reload=False, log_config=None, loop="asyncio", http="h11", ws="none", timeout_graceful_shutdown=15))
        def wait_for_stop():
            kernel.WaitForSingleObject(event, 0xffffffff)
            server.should_exit = True
        watcher = threading.Thread(target=wait_for_stop, daemon=True)
        watcher.start()
        logging.info("Service starting on %s:%s", config.listen_host, config.port)
        server.run()
        if not server.started:
            raise RuntimeError("Service startup did not complete")
        logging.info("Service stopped")
        return 0
    except BaseException:
        logging.exception("Service startup or runtime failed")
        if not silent:
            notify("Service failed to start. Check resources/service_YYYYMMDD.log.", error=True)
        return 1
    finally:
        if event:
            kernel.SetEvent(event)
            if watcher:
                watcher.join(timeout=2)
            kernel.CloseHandle(event)
        if server is not None and server.started:
            for suffix in ("", "-wal", "-shm", "-journal"):
                file = APP_DIRECTORY / "resources" / ("replay.sqlite3" + suffix)
                try:
                    file.unlink(missing_ok=True)
                except OSError:
                    logging.exception("Failed to remove replay database: %s", file.name)
                    if not silent:
                        notify("Service stopped, but replay database cleanup failed. Check resources/service_YYYYMMDD.log.", error=True)
            logging.info("Replay database cleanup completed")
        kernel.ReleaseMutex(mutex)
        kernel.CloseHandle(mutex)
        logging.shutdown()


if __name__ == "__main__":
    silent = "--silent" in sys.argv
    stopping = Path(sys.executable).stem.casefold() == "stopservice" or "--stop" in sys.argv
    try:
        raise SystemExit(stop_service(silent) if stopping else start_service(silent))
    except OSError:
        if not silent:
            notify("Service control failed. Check folder permissions and resources/service_YYYYMMDD.log.", error=True)
        raise SystemExit(1)
