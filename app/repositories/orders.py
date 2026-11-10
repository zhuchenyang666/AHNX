"""订单目录配置与查询记录转换。"""
from app.core.config import server_config

from app.models import CardProgressLogisticsRecordBizBody

ORDER_DATA_DIRECTORY = server_config.order_data_directory


def order_progress(order, status="making", logistics_company=None, logistics_no=None) -> CardProgressLogisticsRecordBizBody:
    return CardProgressLogisticsRecordBizBody(
        orderDate=order.orderDate, orderId=order.orderId,
        branchCode=order.branchCode, cardBizType=order.cardBizType,
        cardFileName=order.cardFileName, coreFileName=order.coreFileName,
        crdPrdSts=status, logisticsCompany=logistics_company, logisticsNo=logistics_no,
    )
