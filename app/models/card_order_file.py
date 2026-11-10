from pydantic import Field

from app.models.base import MessageModel
from app.models.enums import CardBizType
from app.models.validators import CompactDate
class CardOrderFileTransBizBody(MessageModel):
    orderDate: CompactDate = Field(
        ...,
        alias="orderDate",
        max_length=8,
        description="制卡订单的提交日期,格式yyyyMMdd，例如20260812"
    )

    orderId: str = Field(
        ...,
        alias="orderId",
        min_length=1,
        max_length=50,
        description="制卡订单的唯一编号"
    )
    branchCode: str = Field(
        ...,
        alias="branchCode",
        max_length=20,
        description="制卡申请银行端机构编码"
    )
    coreFileName: str = Field(
        ...,
        alias="coreFileName",
        max_length=200,
        description="制卡文件对应的原始核心文件名"
    )
    cardFileName: str = Field(
        ...,
        alias="cardFileName",
        max_length=200,
        description="制卡文件实际文件名"
    )
    cardBizType: CardBizType = Field(
        ...,
        alias="cardBizType",
        description="制卡类型（newcard‑预制卡，changecard‑保号换卡）"
    )
    cardNum: int = Field(
        ...,
        alias="cardNum",
        strict=True,  # 禁止int转str
        description="银行制卡文件中申请的卡张数；取值范围由业务逻辑校验"
    )
    productId: str = Field(
        ...,
        alias="productId",
        max_length=8,
        description="银行端定义的卡产品代码，关联卡产品名称"
    )
    address: str = Field(
        ...,
        alias="address",
        max_length=200,
        description="物流接收的地址"
    )
    recipientName: str = Field(
        ...,
        alias="recipientName",
        max_length=10,
        description="物流接收的人员姓名"
    )
    recipientTel: str = Field(
        ...,
        alias="recipientTel",
        max_length=12,
        description="物流接收的固定电话,格式如010‑12345678,前方010区号为可选"
    )
    recipientPhone: str = Field(
        ...,
        alias="recipientPhone",
        max_length=11,
        description="物流接收的人员手机号码,11位中国大陆手机号"
    )
    remark: str | None = Field(
        default=None,
        alias="remark",
        max_length=100,
        description="备注，支持100个字符以内"
    )

    logisticscompany: str | None = Field(
        default=None, alias="logisticscompany", max_length=50,
        description="物流公司；finished 文件必填，其他状态允许为空",
    )
    logisticsno: str | None = Field(
        default=None, alias="logisticsno", max_length=50,
        description="运单号；finished 文件必填，其他状态允许为空",
    )


class CardOrderFileRequest(MessageModel):
    biz: CardOrderFileTransBizBody = Field(
        ...,
        alias="biz",
        description="SFTP 订单文件的 JSON 内容"
    )
