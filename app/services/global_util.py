from datetime import datetime


def calculate_date_span(start_date: str, end_date: str) -> int:
    """计算两个 yyyyMMdd 日期之间的跨度，允许返回负数, 格式不对会自动抛出异常"""

    start = datetime.strptime(start_date, "%Y%m%d").date()
    end = datetime.strptime(end_date, "%Y%m%d").date()

    return (end - start).days
