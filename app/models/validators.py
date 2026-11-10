"""
报文模型共用的字段校验函数和可复用注解类型,validators.py是对json参数进行格式正确性和逻辑问题校验，不合法返回200
"""

from datetime import datetime
from re import fullmatch
from typing import Annotated, TypeAlias

from pydantic import AfterValidator, StringConstraints

from app.models.patterns import (
    DATE_YYYY_MM_DD_PATTERN,
    DATE_YYYYMMDD_PATTERN,
    TIME_HH_MM_SS_SSS_PATTERN,
)


def validate_date_yyyy_mm_dd(value: str) -> str:
    """校验 yyyy-MM-dd 格式及其表示的公历日期是否真实存在。"""
    if fullmatch(DATE_YYYY_MM_DD_PATTERN, value) is None:
        raise ValueError(f"Invalid date; expected yyyy-MM-dd")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid date; expected yyyy-MM-dd") from exc
    return value


def validate_time_hh_mm_ss_sss(value: str) -> str:
    """校验 HH:mm:ss.SSS 格式及其表示的时间是否真实存在。"""
    if fullmatch(TIME_HH_MM_SS_SSS_PATTERN, value) is None:
        raise ValueError(f"Invalid time; expected HH:mm:ss.SSS")
    try:
        datetime.strptime(value, "%H:%M:%S.%f")
    except ValueError as exc:
        raise ValueError(f"Invalid time; expected HH:mm:ss.SSS") from exc
    return value


def validate_date_yyyymmdd(value: str) -> str:
    """校验 yyyyMMdd 格式及其表示的公历日期是否真实存在。"""
    if fullmatch(DATE_YYYYMMDD_PATTERN, value) is None:
        raise ValueError(f"Invalid date; expected yyyyMMdd")

    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"Invalid date; expected yyyyMMdd") from exc
    return value


# 可直接用于 Pydantic 字段注解；StringConstraints 使正则同时出现在 JSON Schema 中，
# AfterValidator 则进一步排除 2026-02-30 这类格式正确但不存在的日期。
HyphenatedDate: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=DATE_YYYY_MM_DD_PATTERN),
    AfterValidator(validate_date_yyyy_mm_dd),
]

MillisecondTime: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=TIME_HH_MM_SS_SSS_PATTERN),
    AfterValidator(validate_time_hh_mm_ss_sss),
]

CompactDate: TypeAlias = Annotated[
    str,  # 校验基础类型str
    StringConstraints(pattern=DATE_YYYYMMDD_PATTERN),  # 格式校验
    AfterValidator(validate_date_yyyymmdd),  # 存在性进一步校验
]
