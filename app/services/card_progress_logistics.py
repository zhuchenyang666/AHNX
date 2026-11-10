"""制卡进度及物流信息查询服务。"""


from app.models import (
    CardBizType,
    CardProgressLogisticsQueryBizBody,
    CardProgressLogisticsRecordBizBody,
    CardProgressLogisticsRequest,
    CardProgressLogisticsResponse,
    CardProgressLogisticsResult,
)
from app.workers.order_scan import order_scanner
from app.services.esb import BusinessLogicError, EsbQueryService



class CardProgressLogisticsQueryServiceImpl(
    EsbQueryService[
        CardProgressLogisticsRequest,
        CardProgressLogisticsQueryBizBody,
        CardProgressLogisticsRecordBizBody,
        CardProgressLogisticsResponse,
        CardProgressLogisticsResult
    ]
):
    tran_code = "ICCARD12001001"
    serv_cd = "3033000313"
    response_class = CardProgressLogisticsResponse
    record_class = CardProgressLogisticsRecordBizBody
    result_class = CardProgressLogisticsResult
    def load_records(self) -> list[CardProgressLogisticsRecordBizBody]:
        return order_scanner.load_records()


    def validate_query_filters(
            self,
            biz_body: CardProgressLogisticsQueryBizBody,
    ) -> None:
        if biz_body.cardBizType is not None:
            try:
                CardBizType(biz_body.cardBizType)
            except ValueError as exc:
                raise BusinessLogicError(
                    "cardbiztype must be newcard or changecard"
                ) from exc

    def get_record_date(
            self,
            record: CardProgressLogisticsRecordBizBody,
    ) -> str:
        return record.orderDate

    def matches(
            self,
            record: CardProgressLogisticsRecordBizBody,
            biz_body: CardProgressLogisticsQueryBizBody,
    ) -> bool:
        return (
                (
                        biz_body.branchCode is None
                        or biz_body.branchCode == record.branchCode
                )
                and (
                        biz_body.cardFileName is None
                        or biz_body.cardFileName == record.cardFileName
                )
                and (
                        biz_body.cardBizType is None
                        or biz_body.cardBizType == record.cardBizType
                )
        )
