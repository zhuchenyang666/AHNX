"""社保卡回盘查询服务。"""


from app.models import (
    CardBizType,
    SocialCardFeedbackQueryBizBody,
    SocialCardFeedbackRecordBizBody,
    SocialCardFeedbackRequest,
    SocialCardFeedbackResponse,
    SocialCardFeedbackResult,
)
from app.services.esb import BusinessLogicError, EsbQueryService



class SocialCardFeedBackQueryServiceImpl(
    EsbQueryService[
        SocialCardFeedbackRequest,
        SocialCardFeedbackQueryBizBody,
        SocialCardFeedbackRecordBizBody,
        SocialCardFeedbackResponse,
        SocialCardFeedbackResult
    ]
):
    tran_code = "ICCARD12001002"
    serv_cd = "3033000314"
    response_class = SocialCardFeedbackResponse
    record_class = SocialCardFeedbackRecordBizBody
    result_class = SocialCardFeedbackResult
    def load_records(self) -> list[SocialCardFeedbackRecordBizBody]:
        return []


    def validate_query_filters(
            self,
            biz_body: SocialCardFeedbackQueryBizBody,
    ) -> None:
        if biz_body.crdPrdTp is not None:
            try:
                CardBizType(biz_body.crdPrdTp)
            except ValueError as exc:
                raise BusinessLogicError(
                    "crdPrdTp must be newcard or changecard"
                ) from exc

    def get_record_date(
            self,
            record: SocialCardFeedbackRecordBizBody,
    ) -> str:
        return record.crdPrdDt

    def matches(
            self,
            record: SocialCardFeedbackRecordBizBody,
            biz_body: SocialCardFeedbackQueryBizBody,
    ) -> bool:
        return (
                (
                        biz_body.blngInstId is None
                        or biz_body.blngInstId == record.blngInstId
                )
                and (
                        biz_body.crdPrdTp is None
                        or biz_body.crdPrdTp == record.crdPrdTp
                )
                and (
                        biz_body.socInsFileBtcNum is None
                        or biz_body.socInsFileBtcNum == record.socInsFileBtcNum
                )
        )
