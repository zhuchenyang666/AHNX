"""社保卡制卡回盘文件查询报文。"""

from pydantic import Field

from app.models.base import MessageModel
from app.models.esb import EsbRequest, EsbResponse, PagedQueryBizBody


class SocialCardFeedbackQueryBizBody(PagedQueryBizBody):
    """请求 ``bizBody``，字段顺序与接口文档一致。"""
    blngInstId: str | None = Field(
        default=None,
        alias="blnginstid",
        max_length=20,
        description="制卡申请机构号；未输入时不按机构筛选",
    )
    crdPrdTp: str | None = Field(
        default=None,
        alias="crdprdtp",
        max_length=10,
        description="制卡类型：newcard-预制卡，changecard-保号换卡",
    )
    socInsFileBtcNum: str | None = Field(
        default=None,
        alias="socinsfilebtcnum",
        max_length=256,
        description="人社系统批次号，一般为 8 位纯数字，精确匹配",
    )


class SocialCardFeedbackRecordBizBody(MessageModel):
    """响应 ``records`` 中的一条社保卡回盘文件记录。"""

    blngInstId: str = Field(
        ...,
        alias="blnginstid",
        max_length=20,
        description="制卡申请机构代码"
    )
    socInsFileBtcNum: str = Field(
        ...,
        alias="socinsfilebtcnum",
        max_length=256,
        description="社保批次号"
    )
    crdPrdTp: str = Field(
        ...,
        alias="crdprdtp",
        max_length=10,
        description="制卡类型：newcard-预制卡，changecard-保号换卡",
    )
    city: str = Field(
        ...,
        alias="city",
        max_length=20,
        description="所属地市级区域"
    )
    crdPrdDt: str = Field(
        ...,
        alias="crdprddt",
        max_length=8,
        description="制卡日期，格式为 yyyyMMdd"
    )
    socScNo: str = Field(
        ...,
        alias="socscno",
        max_length=60,
        description="社保卡号段"
    )
    bnkCardNo: str = Field(
        ...,
        alias="bnkcardno",
        max_length=60,
        description="银行卡号段区间"
    )
    trncNo: str = Field(
        ...,
        alias="trncno",
        max_length=60,
        description="交通卡号段区间"
    )
    bldgInfo: str | None = Field(
        default=None,
        alias="bldginfo",
        max_length=120,
        description="社保卡关联的楼宇或建筑信息",
    )
    othr: str | None = Field(
        default=None,
        alias="othr",
        max_length=256,
        description="其他备注信息，例如地市特色应用",
    )


class SocialCardFeedbackResult(MessageModel):
    """响应 ``bizBody``。"""

    count: int = Field(
        ...,
        alias="count",
        strict=True,
        description="符合查询条件的记录总数，无数据时为 0"
    )
    records: list[SocialCardFeedbackRecordBizBody] = Field(
        default_factory=list,
        alias="records",
        strict=True,
        description="社保卡制卡回盘文件信息列表，无数据时为空数组",
    )


class SocialCardFeedbackRequest(EsbRequest[SocialCardFeedbackQueryBizBody]):
    """社保卡制卡回盘文件查询完整请求报文。"""


class SocialCardFeedbackResponse(EsbResponse[SocialCardFeedbackResult]):
    """社保卡制卡回盘文件查询完整响应报文。"""
