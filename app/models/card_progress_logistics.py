"""制卡进度及物流信息查询报文。"""

from typing import Self

from pydantic import Field, model_validator
from app.models.enums import CrdPrdSts
from app.models.base import MessageModel
from app.models.esb import EsbRequest, EsbResponse, PagedQueryBizBody


class CardProgressLogisticsQueryBizBody(PagedQueryBizBody):
    """请求 ``bizBody``，字段顺序与接口文档一致。"""
    branchCode: str | None = Field(
        default=None,
        alias="branchcode",
        max_length=20,
        description="制卡申请机构代码；未输入时不按机构筛选",
    )
    cardFileName: str | None = Field(
        default=None,
        alias="cardfilename",
        max_length=200,
        description="制卡文件名称，精确匹配",
    )
    cardBizType: str | None = Field(
        default=None,
        alias="cardbiztype",
        max_length=10,
        description="制卡业务类型：newcard-预制卡，changecard-保号换卡",
    )


class CardProgressLogisticsRecordBizBody(MessageModel):
    """响应 ``records`` 中的一条制卡进度及物流记录。"""
    orderDate: str = Field(
        ...,
        alias="orderdate",
        max_length=8,
        description="订单提交日期，格式为 yyyyMMdd",
    )
    orderId: str = Field(
        ...,
        alias="orderid",
        max_length=50,
        description="制卡订单唯一编号"
    )
    branchCode: str = Field(
        ...,
        alias="branchcode",
        max_length=20,
        description="制卡申请机构代码"
    )
    cardBizType: str = Field(
        ...,
        alias="cardbiztype",
        max_length=10,
        description="制卡业务类型：newcard-预制卡，changecard-保号换卡",
    )
    cardFileName: str = Field(
        ...,
        alias="cardfilename",
        max_length=200,
        description="制卡文件名称"
    )
    coreFileName: str = Field(
        ...,
        alias="corefilename",
        max_length=200,
        description="核心文件名称"
    )
    crdPrdSts: CrdPrdSts = Field(
        ...,
        alias="crdprdsts",
        description="制卡状态：pending-待制卡，making-制卡中，finished-制卡完成",
    )
    logisticsCompany: str | None = Field(
        default=None,
        alias="logisticscompany",
        max_length=50,
        description="承运物流公司名称；未发货时为空",
    )
    logisticsNo: str | None = Field(
        default=None,
        alias="logisticsno",
        max_length=50,
        description="快递运单编号；未发货时为空",
    )

    @model_validator(mode="after")
    def validate_finished_logistics(self) -> Self:
        if self.crdPrdSts == CrdPrdSts.FINISHED and not (self.logisticsCompany and self.logisticsNo):
            raise ValueError("finished requires non-empty logisticscompany and logisticsno")
        return self


class CardProgressLogisticsResult(MessageModel):
    """响应 ``bizBody``。"""

    count: int = Field(
        ...,
        alias="count",
        strict=True,
        description="符合查询条件的记录总数，无数据时为 0"
    )
    records: list[CardProgressLogisticsRecordBizBody] = Field(
        default_factory=list,
        alias="records",
        strict=True,
        description="制卡进度及物流信息列表，无数据时为空数组",
    )


class CardProgressLogisticsRequest(EsbRequest[CardProgressLogisticsQueryBizBody]):
    """制卡进度及物流信息查询完整请求报文。"""


class CardProgressLogisticsResponse(EsbResponse[CardProgressLogisticsResult]):
    """制卡进度及物流信息查询完整响应报文。"""
