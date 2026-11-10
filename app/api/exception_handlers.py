"""仅使用 200、404、500；参数和业务失败通过 ESB 报文返回。"""
from datetime import datetime

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from app.models.esb import EsbResponse, EmptyBizBody, RequestSysHeader
from app.models.enums import BizResCode


async def parameter_error(request: Request, message: str) -> JSONResponse:
    message = message.encode("ascii", "backslashreplace").decode("ascii")
    now = datetime.now().astimezone()
    defaults = dict(servCd="", globalSq="", rqstDate=now.strftime("%Y-%m-%d"),
                    rqstTime=now.strftime("%H:%M:%S.%f")[:12], rqstSysCd="", prvdSysCd="", tranCode="")
    raw_header = {}
    try:
        payload = await request.json()
        raw_header = payload["Transaction"]["Header"]["sysHeader"]
    except (ValueError, KeyError, TypeError):
        pass
    header_data = dict(defaults)
    if isinstance(raw_header, dict):
        header_data.update({key: value for key, value in raw_header.items() if key in RequestSysHeader.model_fields})
    try:
        header = RequestSysHeader.from_dict(header_data)
    except ValidationError as exc:
        # 无效请求头不能阻止返回参数错误；仅回显可通过校验的字段。
        for error in exc.errors():
            key = error["loc"][0]
            header_data[key] = defaults.get(key)
        header = RequestSysHeader.from_dict(header_data)
    response = EsbResponse.from_request_sys_header(
        header, biz_body=EmptyBizBody(), biz_res_cd=BizResCode.PARAMETER_VALIDATOR_UNEXPECTED,
        res_text=message[:100],
    )
    response.transaction.header.sysHeader.bizResText = message[:500]
    return JSONResponse(status_code=200, content=response.to_dict())


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content={"msg": "url not found", "code": 404})
    if exc.status_code >= 500:
        return JSONResponse(status_code=500, content={"msg": "ks server error", "code": 500})
    message = "Method not allowed; this endpoint only accepts POST" if exc.status_code == 405 else str(exc.detail)
    return await parameter_error(request, message)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
    details = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"] if part != "body")
        details.append(f"{location or 'JSON'}: {error['msg']}")
    return await parameter_error(request, "Invalid request parameters: " + "; ".join(details))


async def internal_exception_handler(request: Request, exc: Exception) -> Response:
    return JSONResponse(status_code=500, content={"msg": "ks server error", "code": 500})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, internal_exception_handler)
