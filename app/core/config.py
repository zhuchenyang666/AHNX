"""公共配置与本地、正式环境配置。"""
import os
import re
import sys
from pathlib import Path
from app.paths import APP_DIRECTORY
from typing import Literal

from pydantic import BaseModel, Field
from yaml import safe_load


class EnvironmentConfig(BaseModel):
    host: str
    port: int = Field(ge=1, le=65535)
    listen_host: str = Field(alias="listen-host")
    reload: bool

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class Environments(BaseModel):
    local: EnvironmentConfig
    production: EnvironmentConfig


class ServerConfig(BaseModel):
    active: Literal["local", "production"]
    sftppath: str = "./安徽农信借记卡订单文件"
    scan_interval_ms: int = Field(default=3_600_000, alias="scan-interval-ms", gt=0, strict=True)
    rootpath: str
    ks_code: str = Field(alias="ks-code")
    version: str
    title: str
    environments: Environments

    @property
    def order_data_directory(self) -> Path:
        return (APP_DIRECTORY / self.sftppath.strip() / "data").resolve()

    @property
    def environment(self) -> EnvironmentConfig:
        return getattr(self.environments, self.active)


CONFIG_FILE = APP_DIRECTORY / "resources" / "application.yaml"


def load_application_yaml() -> ServerConfig:
    content = CONFIG_FILE.read_text(encoding="utf-8")
    # Windows 路径按字面值读取，同时兼容原先双反斜杠的写法，避免 \t 等被 YAML 转义。
    content = re.sub(
        r'(?m)^([ \t]*sftppath:[ \t]*)"((?:[A-Za-z]:|\.{1,2})\\[^"\r\n]*)"([ \t]*(?:#[^\r\n]*)?)$',
        lambda match: match[1] + "'" + match[2].replace("\\\\", "\\").replace("'", "''") + "'" + match[3],
        content,
    )
    data = safe_load(content)["server"]
    if not getattr(sys, "frozen", False) and "AHNX_ENV" in os.environ:
        data["active"] = os.environ["AHNX_ENV"]
    return ServerConfig.model_validate(data)


server_config = load_application_yaml()
