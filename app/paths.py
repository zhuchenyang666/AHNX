"""配置、订单和运行文件统一位于程序目录。"""
import sys
from pathlib import Path

APP_DIRECTORY = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
