"""构建 Windows 单文件服务端和测试客户端：python build_service.py。"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "dist").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="package-", dir=ROOT / "build") as staging:
        output = Path(staging) / "AHNX-Service"
        targets = (
            ("AHNX-Service", "service_launcher.py", [
                "--exclude-module", "tkinter", "--exclude-module", "ui",
                "--hidden-import", "uvicorn.loops.asyncio",
                "--hidden-import", "uvicorn.protocols.http.h11_impl",
                "--hidden-import", "uvicorn.lifespan.on",
            ]),
            ("AHNX-TestClient", "ui/client.py", []),
        )
        for name, entry, options in targets:
            subprocess.run([
                sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
                "--name", name, "--distpath", str(output),
                "--workpath", str(ROOT / "build" / "pyinstaller"), "--specpath", str(ROOT / "build"),
                "--paths", str(ROOT), "--exclude-module", "tests", *options, str(ROOT / entry),
            ], cwd=ROOT, check=True)
        resources = output / "resources"
        resources.mkdir()
        shutil.copy2(ROOT / "resources" / "application.yaml", resources / "application.yaml")
        (output / "使用说明.txt").write_text(r"""安徽农信服务与测试客户端（Windows x64）

1. 解压整个目录到可读写的位置。两个 EXE 各自内置运行库，resources/application.yaml 保持外置。
2. 发布包原样复制项目 resources/application.yaml，不再强制切换环境。
   active: local 监听 127.0.0.1:8000；active: production 使用 production 地址和端口。
   EXE 以同目录 YAML 的 active 为准，不读取 AHNX_ENV；EXE 始终关闭自动重载。
   切换本地环境：修改 server.active 为 local，保存后先停止再重新启动。
3. 双击 AHNX-Service.exe 启动后台服务；双击 AHNX-TestClient.exe 打开测试界面。
   客户端连接地址以 resources/application.yaml 的环境配置为准。
4. 在程序目录运行 .\AHNX-Service.exe --stop 正常停止服务。
   启动成功或失败均弹出英文提示框；成功框不会阻塞接口服务。
   正常关闭服务后自动删除 resources/replay.sqlite3，下一次请求重新创建。
5. 日志位于 resources/service_YYYYMMDD.log。启动失败时检查该文件和端口占用。
6. data/yyyyMMdd/ 为原始订单和制卡文件，只读，不修改、不移动、不删除。
   report/orders.sqlite3 为唯一结果数据库，订单号为主键，状态由文件名前缀决定。
   pending/making/finished_日期.txt 每行一个 JSON，忽略空行。每轮全量重读并更新。
7. resources/replay.sqlite3 为本次运行的接口防重放记录，正常关闭后清空。
   升级时先停止服务，保留目标机器原有配置、data 和整个 report。
   旧版 resources 及 report 分日期库不再读取；以新 report/orders.sqlite3 为准。
   server.sftppath 直接填写订单根目录，默认 ./安徽农信借记卡订单文件。
   server.scan-interval-ms 为扫描间隔（毫秒），按配置扫描当天，凌晨补扫昨天。
   发布包不包含订单数据。将 sftppath 指向现场订单目录，启动时自动创建缺失的 data 和 report。
8. 同一 Windows 登录会话内请使用相同账号启动和停止。
   本程序不是 Windows 系统服务，退出登录后不保证运行，不自动开机启动。
9. 目标机器不需要安装 Python；需要匹配的 Windows x64 环境。
""", encoding="utf-8-sig")
        archive = shutil.make_archive(str(ROOT / "dist" / "AHNX-Service-Windows-x64"), "zip", staging, output.name)
    print(archive)


if __name__ == "__main__":
    build()
