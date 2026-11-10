"""ESB 分页查询接口共用的执行流程。"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from app.models.base import MessageModel
from app.models.enums import BizResCode
from app.models.esb import EmptyBizBody, EsbRequest, EsbResponse, PagedQueryBizBody
from app.models.validators import (
    validate_date_yyyy_mm_dd,
    validate_date_yyyymmdd,
    validate_time_hh_mm_ss_sss,
)
from app.security.replay import validate_and_claim
from app.services.global_util import calculate_date_span

RequestT = TypeVar("RequestT", bound=EsbRequest[Any])
RequestBizBodyT = TypeVar("RequestBizBodyT", bound=PagedQueryBizBody)
RecordT = TypeVar("RecordT", bound=MessageModel)
ResponseT = TypeVar("ResponseT", bound=EsbResponse[Any])
ResponseBizBodyT = TypeVar("ResponseBizBodyT", bound=MessageModel)


class BusinessLogicError(ValueError):
    """需要转换为 HTTP 200 ESB 错误响应的业务异常。"""

    def __init__(
            self,
            message: str,
            biz_res_cd: BizResCode = BizResCode.REQUEST_LOGIC_ERROR,
    ) -> None:
        super().__init__(message)
        self.biz_res_cd = biz_res_cd


class EsbQueryService(
    ABC,  # 抽象基类
    Generic[
        RequestT,  # execute() 的请求类型
        RequestBizBodyT,  # validate/matches 的查询条件
        RecordT,  # 单条 Mock 记录类型
        ResponseT,  # execute() 的返回类型
        ResponseBizBodyT  # bizBody 结果类型
    ],
):
    """封装 ESB 分页日期查询共有的校验、筛选和响应转换流程。"""

    response_class: type[ResponseT]
    record_class: type[RecordT]
    result_class: type[ResponseBizBodyT]
    tran_code: str
    serv_cd: str

    async def execute(self, request: RequestT) -> ResponseT:
        request_biz_body = request.transaction.body.request.bizBody
        header = request.transaction.header.sysHeader
        if (header.tranCode, header.servCd) != (self.tran_code, self.serv_cd):
            return self.response_class.from_request(
                request,
                biz_body=self.build_result(0, []),
                biz_res_cd=BizResCode.REQUEST_LOGIC_ERROR,
                res_text=f"tranCode/servCd mismatch: expected {self.tran_code}/{self.serv_cd}",
            )
        try:
            self.validate_header(request)
            if isinstance(request_biz_body, EmptyBizBody):
                return self.response_class.success_from_request(request)
            typed_biz_body = request_biz_body
            self.validate_request(typed_biz_body)
            result = await self.query(typed_biz_body)
        except BusinessLogicError as exc:
            return self.response_class.logic_error_from_request(
                request,
                str(exc),
                biz_res_cd=exc.biz_res_cd,
            )

        return self.response_class.success_from_request(
            request,
            biz_body=result,
        )

    @staticmethod
    def validate_header(request: RequestT) -> None:
        """校验所有 ESB 查询接口共用的请求头日期和时间。"""
        sys_header = request.transaction.header.sysHeader
        try:
            validate_date_yyyy_mm_dd(sys_header.rqstDate)
            validate_time_hh_mm_ss_sss(sys_header.rqstTime)
            validate_and_claim(sys_header)
        except ValueError as exc:
            raise BusinessLogicError(str(exc)) from exc

    def validate_request(self, biz_body: RequestBizBodyT) -> None:
        """校验公共分页、日期字段及接口特有筛选条件。"""
        if biz_body.page < 1:
            raise BusinessLogicError("page must be at least 1")

        if not 10 <= biz_body.limit <= 1000:
            raise BusinessLogicError("limit must be between 10 and 1000")

        for field_name, value in (
                ("startdate", biz_body.startDate),
                ("enddate", biz_body.endDate),
        ):
            if value:
                try:
                    validate_date_yyyymmdd(value)
                except ValueError as exc:
                    raise BusinessLogicError(
                        f"{field_name} must be a valid date in yyyyMMdd format"
                    ) from exc

        self.validate_query_filters(biz_body)

    def validate_query_filters(self, biz_body: RequestBizBodyT) -> None:
        """校验接口特有筛选字段；没有额外规则时无需覆盖。"""

    def load_records(self) -> list[RecordT]:
        """由具体服务提供查询记录。"""
        raise NotImplementedError("The query service must provide a data source")

    async def query(self, biz_body: RequestBizBodyT) -> ResponseBizBodyT:
        """执行公共日期筛选、业务筛选、排序和分页。"""
        if biz_body.startDate and biz_body.endDate:
            span = calculate_date_span(biz_body.startDate, biz_body.endDate)
            if span < 0:
                raise BusinessLogicError("startdate must not be later than enddate")
            if span > 90:
                raise BusinessLogicError("Date range must not exceed 90 days", BizResCode.TIME_SPAN_ERROR)
        records = self.load_records()
        if not records:
            return self.build_result(0, [])

        available_dates = [
            self.get_record_date(record)
            for record in records
        ]
        start_date = biz_body.startDate or min(available_dates)
        end_date = biz_body.endDate or max(available_dates)

        date_span = calculate_date_span(start_date, end_date)
        if date_span > 90:
            raise BusinessLogicError(
                "Date range must not exceed 90 days",
                biz_res_cd=BizResCode.TIME_SPAN_ERROR,
            )
        if date_span < 0:
            raise BusinessLogicError("startdate must not be later than enddate")

        filtered_records = [
            record
            for record in records
            if start_date <= self.get_record_date(record) <= end_date
               and self.matches(record, biz_body)
        ]
        filtered_records.sort(
            key=self.get_record_date,
            reverse=True,
        )

        total = len(filtered_records)
        offset = (biz_body.page - 1) * biz_body.limit
        page_records = filtered_records[offset:offset + biz_body.limit]
        return self.build_result(total, page_records)

    def build_result(
            self,
            count: int,
            records: list[RecordT],
    ) -> ResponseBizBodyT:
        """使用具体服务声明的结果模型构造分页响应业务体。"""
        return self.result_class.from_dict(
            {"count": count, "records": records}
        )

    @abstractmethod
    def get_record_date(self, record: RecordT) -> str:
        """返回具体记录用于筛选和排序的 yyyyMMdd 日期。"""

    @abstractmethod
    def matches(
            self,
            record: RecordT,
            biz_body: RequestBizBodyT,
    ) -> bool:
        """判断记录是否符合接口特有筛选条件。"""
