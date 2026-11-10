from datetime import datetime
from uuid import uuid4
import asyncio
import unittest

from app.api.v1.endpoints.social_card_feedback import query_social_card_feedback
from app.models import (
    BizResCode,
    EmptyBizBody,
    SocialCardFeedbackRequest,
    SocialCardFeedbackResult,
)


def make_request(biz_body: dict) -> SocialCardFeedbackRequest:
    return SocialCardFeedbackRequest.model_validate(
        {
            "Transaction": {
                "Body": {"request": {"bizBody": biz_body}},
                "Header": {
                    "sysHeader": {
                        "servCd": "3033000314",
                        "globalSq": "029" + uuid4().hex[:26],
                        "rqstDate": datetime.now().strftime("%Y-%m-%d"),
                        "rqstTime": datetime.now().strftime("%H:%M:%S.%f")[:12],
                        "rqstSysCd": "029",
                        "prvdSysCd": "662",
                        "tranCode": "ICCARD12001002",
                    }
                },
            }
        }
    )


class SocialCardFeedbackQueryTests(unittest.TestCase):
    def query(self, biz_body: dict):
        return asyncio.run(query_social_card_feedback(make_request(biz_body)))

    def test_empty_biz_body_returns_success(self) -> None:
        response = self.query({})
        self.assertIsInstance(response.transaction.body.response.bizBody, EmptyBizBody)
        self.assertEqual(
            response.transaction.header.sysHeader.bizResCd,
            BizResCode.SUCCESS,
        )

    def test_paginates_and_sorts_by_production_date_descending(self) -> None:
        response = self.query({"page": 2, "limit": 10})
        result = response.transaction.body.response.bizBody

        self.assertIsInstance(result, SocialCardFeedbackResult)
        self.assertEqual(result.count, 0)
        self.assertEqual(len(result.records), 0)
        dates = [record.crdPrdDt for record in result.records]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_filters_by_institution_type_and_batch(self) -> None:
        institution_result = self.query(
            {"page": 1, "limit": 10, "blnginstid": "3401000001"}
        ).transaction.body.response.bizBody
        self.assertEqual(institution_result.count, 0)

        type_result = self.query(
            {"page": 1, "limit": 10, "crdprdtp": "newcard"}
        ).transaction.body.response.bizBody
        self.assertEqual(type_result.count, 0)

        batch_result = self.query(
            {"page": 1, "limit": 10, "socinsfilebtcnum": "20260806"}
        ).transaction.body.response.bizBody
        self.assertEqual(batch_result.count, 0)

    def test_invalid_type_returns_business_error(self) -> None:
        response = self.query(
            {"page": 1, "limit": 10, "crdprdtp": "invalid"}
        )
        header = response.transaction.header.sysHeader
        self.assertEqual(header.bizResCd, BizResCode.REQUEST_LOGIC_ERROR)
        self.assertEqual(header.resText, "crdPrdTp must be newcard or changecard")

    def test_more_than_90_days_returns_time_span_error(self) -> None:
        response = self.query(
            {
                "page": 1,
                "limit": 10,
                "startdate": "20260101",
                "enddate": "20260601",
            }
        )
        header = response.transaction.header.sysHeader
        self.assertEqual(header.bizResCd, BizResCode.TIME_SPAN_ERROR)
        self.assertEqual(header.resText, "Date range must not exceed 90 days")


if __name__ == "__main__":
    unittest.main()
