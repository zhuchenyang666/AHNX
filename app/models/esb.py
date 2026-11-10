"""所有接口共用的 ESB 报文结构。

请求泛型 ``RequestBizBodyT`` 和响应泛型 ``ResponseBizBodyT``
分别代表请求、响应最内层的 ``bizBody``。外层 JSON 层级在这里定义一次：

Transaction -> Body -> request/response -> bizBody
            -> Header -> sysHeader
"""

from datetime import datetime

from typing import Any, Generic, Self, TypeVar, cast

from pydantic import Field

from app.models.base import MessageModel
from app.models.enums import BizResCode

RequestBizBodyT = TypeVar("RequestBizBodyT", bound=MessageModel)
ResponseBizBodyT = TypeVar("ResponseBizBodyT", bound=MessageModel)


class RequestSysHeader(MessageModel):
    """ESB 请求系统报文头。"""

    servCd: str = Field(
        ...,
        alias="servCd",
        max_length=10,
        description="ESB 服务编码"
    )
    globalSq: str = Field(
        ...,
        alias="globalSq",
        max_length=32,
        description="全局流水号；规范表格标注 29 位，但需求示例为 32 位",
    )
    msgId: str | None = Field(
        default=None,
        alias="msgId",
        max_length=32,
        description="消息流水号"
    )
    initRqstSysCd: str | None = Field(
        default=None,
        alias="initRqstSysCd",
        max_length=3,
        description="初始请求系统代码",
    )
    rqstDate: str = Field(
        ...,
        alias="rqstDate",
        min_length=10,
        max_length=10,
        description="请求方消息日期，格式为 yyyy-MM-dd",
    )
    rqstTime: str = Field(
        ...,
        alias="rqstTime",
        min_length=12,
        max_length=12,
        description="请求方消息时间，格式为 HH:mm:ss.SSS",
    )
    rqstSysCd: str = Field(
        ...,
        alias="rqstSysCd",
        max_length=3,
        description="请求方系统编码"
    )
    prvdSysCd: str = Field(
        ...,
        alias="prvdSysCd",
        max_length=3,
        description="提供方系统编码"
    )
    tranCode: str = Field(
        ...,
        alias="tranCode",
        max_length=32,
        description="服务交易码"
    )
    nodeInfo: str | None = Field(
        default=None,
        alias="nodeInfo",
        max_length=100,
        description="系统节点信息"
    )
    orgCd: str | None = Field(
        default=None,
        alias="orgCd",
        max_length=10,
        description="机构编号"
    )
    termCd: str | None = Field(
        default=None,
        alias="termCd",
        max_length=64,
        description="终端设备编号"
    )
    operation: str | None = Field(
        default=None,
        alias="operation",
        max_length=15,
        description="服务操作"
    )
    bizId: str | None = Field(
        default=None,
        alias="bizId",
        max_length=20,
        description="业务主键"
    )
    bizType: str | None = Field(
        default=None,
        alias="bizType",
        max_length=20,
        description="业务类别"
    )
    extend: str | None = Field(
        default=None,
        alias="extend",
        max_length=200,
        description="预留字段"
    )
    extend1: str | None = Field(
        default=None,
        alias="extend1",
        max_length=200,
        description="预留字段 1"
    )


class ResponseSysHeader(RequestSysHeader):
    """ESB 响应系统报文头，在请求头基础上增加响应字段。"""

    prvdDate: str = Field(
        ...,
        alias="prvdDate",
        max_length=10,
        description="提供方消息日期，格式为 yyyy-MM-dd",
    )
    prvdTime: str = Field(
        ...,
        alias="prvdTime",
        min_length=12,
        max_length=12,
        description="提供方消息时间，格式为 HH:mm:ss.SSS",
    )
    tranStsCd: str | None = Field(
        default=None,
        alias="tranStsCd",
        max_length=1,
        description="交易状态码"
    )
    resCd: str | None = Field(
        default=None,
        alias="resCd",
        max_length=10,
        description="DSP 响应码"
    )
    resText: str | None = Field(
        default=None,
        alias="resText",
        max_length=100,
        description="DSP 响应信息"
    )
    bizResCd: str = Field(
        ...,
        alias="bizResCd",
        max_length=10,
        description="提供方业务响应码；AAAAAAA 表示交易成功,其余按枚举定义",
    )
    bizResText: str = Field(
        ...,
        alias="bizResText",
        max_length=500,
        description="提供方业务响应信息,根据bizResCd枚举查询得到",
    )

    @classmethod
    def from_request(
            cls,
            request_sys_header: RequestSysHeader | dict[str, Any],
            *,
            tran_sts_cd: str | None = None,
            res_cd: str | None = None,
            res_text: str | None = None,
            biz_res_cd: BizResCode = BizResCode.SUCCESS,
    ) -> Self:
        # RequestSysHeader对象转字典
        if isinstance(request_sys_header, RequestSysHeader):
            request_sys_header = RequestSysHeader.to_dict(request_sys_header)
        now = datetime.now().astimezone()
        return cls(
            **request_sys_header,
            prvdDate=now.strftime("%Y-%m-%d"),
            prvdTime=now.strftime("%H:%M:%S.%f")[:12],
            tranStsCd=tran_sts_cd,
            resCd=res_cd,
            resText=res_text,
            bizResCd=biz_res_cd,
            bizResText=res_text or biz_res_cd.text,
        )


class RequestHeader(MessageModel):
    sysHeader: RequestSysHeader = Field(
        ...,
        alias="sysHeader",
        description="请求 ESB 系统报文头"
    )


class ResponseHeader(MessageModel):
    sysHeader: ResponseSysHeader = Field(
        ...,
        alias="sysHeader",
        description="响应 ESB 系统报文头"
    )


class EmptyBizBody(MessageModel):
    """只允许空对象 {}。"""
    # model_config = ConfigDict(extra="forbid")


class RequestContent(MessageModel, Generic[RequestBizBodyT]):
    """请求业务体容器；bizBody 必须存在，可为 {} 或具体请求模型。"""

    bizBody: EmptyBizBody | RequestBizBodyT = Field(
        ...,
        alias="bizBody",
        description="业务体字段必须存在且不能为 null；允许为空对象 {}"
    )


class ResponseContent(MessageModel, Generic[ResponseBizBodyT]):
    """响应业务体容器；bizBody 必须存在，可为 {} 或具体响应模型。"""

    bizBody: EmptyBizBody | ResponseBizBodyT = Field(
        ...,
        alias="bizBody",
        description="业务体字段必须存在且不能为 null；允许为空对象 {}",
    )


class RequestBody(MessageModel, Generic[RequestBizBodyT]):
    request: RequestContent[RequestBizBodyT] = Field(
        ...,
        alias="request",
        description="请求报文容器"
    )


class ResponseBody(MessageModel, Generic[ResponseBizBodyT]):
    response: ResponseContent[ResponseBizBodyT] = Field(
        ...,
        alias="response",
        description="响应报文容器"
    )


class RequestTransaction(MessageModel, Generic[RequestBizBodyT]):
    body: RequestBody[RequestBizBodyT] = Field(
        ...,
        alias="Body",
        description="ESB 请求体"
    )
    header: RequestHeader = Field(
        ...,
        alias="Header",
        description="ESB 请求头"
    )


class ResponseTransaction(MessageModel, Generic[ResponseBizBodyT]):
    body: ResponseBody[ResponseBizBodyT] = Field(
        ...,
        alias="Body",
        description="ESB 响应体"
    )
    header: ResponseHeader = Field(
        ...,
        alias="Header",
        description="ESB 响应头"
    )


class EsbRequest(MessageModel, Generic[RequestBizBodyT]):
    """完整 ESB 请求；具体接口只需指定一次业务请求体类型。"""

    transaction: RequestTransaction[RequestBizBodyT] = Field(
        ...,
        alias="Transaction",
        description="ESB 请求交易报文"
    )


class EsbResponse(MessageModel, Generic[ResponseBizBodyT]):
    """完整 ESB 响应；具体接口只需指定一次业务响应体类型。"""

    transaction: ResponseTransaction[ResponseBizBodyT] = Field(
        ...,
        alias="Transaction",
        description="ESB 响应交易报文",
    )

    @classmethod
    def from_request_sys_header(
            cls,
            request_sys_header: RequestSysHeader | dict[str, Any],
            *,
            biz_body: EmptyBizBody | ResponseBizBodyT,
            biz_res_cd: BizResCode = BizResCode.SUCCESS,
            res_text: str | None = None,
    ) -> Self:
        response_sys_header = ResponseSysHeader.from_request(
            request_sys_header=request_sys_header,
            biz_res_cd=biz_res_cd,
            res_cd=biz_res_cd if biz_res_cd != BizResCode.SUCCESS else None,
            res_text=res_text,
        )
        return cast(
            Self,
            cls.from_dict(
                {
                    "Transaction": {
                        "Body": {"response": {"bizBody": biz_body}},
                        "Header": {"sysHeader": response_sys_header},
                    }
                }
            ),
        )

    @classmethod
    def from_request(
            cls,
            request: EsbRequest[Any] | dict[str, Any],
            *,
            biz_body: EmptyBizBody | ResponseBizBodyT,
            biz_res_cd: BizResCode = BizResCode.SUCCESS,
            res_text: str | None = None,
    ) -> Self:
        """根据请求报文和业务结果构造完整 ESB 响应。"""
        if isinstance(request, EsbRequest):
            request = EsbRequest.to_dict(request)
        return cast(
            Self,
            cls.from_request_sys_header(
                request["Transaction"]["Header"]["sysHeader"],
                biz_body=biz_body,
                biz_res_cd=biz_res_cd,
                res_text=res_text,
            ),
        )

    @classmethod
    def success_from_request(
            cls,
            request: EsbRequest[Any] | dict[str, Any],
            biz_body: EmptyBizBody | ResponseBizBodyT | None = None,
    ) -> Self:
        """根据请求构造成功响应。"""
        return cast(
            Self,
            cls.from_request(
                request,
                biz_body=biz_body if biz_body is not None else EmptyBizBody(),
            ),
        )

    @classmethod
    def logic_error_from_request(
            cls,
            request: EsbRequest[Any] | dict[str, Any],
            message: str,
            biz_res_cd: BizResCode = BizResCode.REQUEST_LOGIC_ERROR,
    ) -> Self:
        """根据请求构造业务规则错误响应，HTTP 状态码仍为 200。"""
        return cast(
            Self,
            cls.from_request(
                request,
                biz_body=EmptyBizBody(),
                biz_res_cd=biz_res_cd,
                res_text=message,
            ),
        )


class PagedQueryBizBody(MessageModel):
    """请求查询参数通用字段"""
    page: int = Field(
        ...,
        alias="page",
        strict=True,
        description="当前页码",
    )
    limit: int = Field(
        ...,
        alias="limit",
        strict=True,
        description="每页记录数",
    )
    startDate: str | None = Field(
        default=None,
        alias="startdate",
        max_length=8,
        description="开始日期，格式为 yyyyMMdd",
    )
    endDate: str | None = Field(
        default=None,
        alias="enddate",
        max_length=8,
        description="结束日期，格式为 yyyyMMdd",
    )
