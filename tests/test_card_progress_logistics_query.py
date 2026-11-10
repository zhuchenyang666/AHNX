from datetime import datetime
from uuid import uuid4
import asyncio
import unittest

from pydantic import ValidationError

from app.api.v1.endpoints.card_progress_logistics import (
    query_card_progress_logistics,
)
from app.models import (
    BizResCode,
    CardProgressLogisticsRequest,
    CardProgressLogisticsResult,
    EmptyBizBody,
    CardOrderFileTransBizBody,
    SocialCardFeedbackQueryBizBody,
)


def make_request(biz_body: dict) -> CardProgressLogisticsRequest:
    return CardProgressLogisticsRequest.model_validate(
        {
            "Transaction": {
                "Body": {"request": {"bizBody": biz_body}},
                "Header": {
                    "sysHeader": {
                        "servCd": "3033000313",
                        "globalSq": "029" + uuid4().hex[:26],
                        "rqstDate": datetime.now().strftime("%Y-%m-%d"),
                        "rqstTime": datetime.now().strftime("%H:%M:%S.%f")[:12],
                        "rqstSysCd": "029",
                        "prvdSysCd": "662",
                        "tranCode": "ICCARD12001001",
                    }
                },
            }
        }
    )


class CardProgressLogisticsQueryTests(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from app.security.replay import BANK_TIMEZONE
        from app.workers.order_scan import OrderScanner
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        import shutil
        directory = Path(temporary.name) / "data"
        folder = directory / "20260914"
        folder.mkdir(parents=True)
        shutil.copy2(Path(__file__).parent / "fixtures" / "finished_20260914.txt", folder)
        scanner = OrderScanner(directory)
        scanner.initialize()
        for folder in directory.iterdir():
            if folder.is_dir():
                scanner.scan_day(datetime.strptime(folder.name, "%Y%m%d").date(), datetime.now(BANK_TIMEZONE))
        mock = patch("app.services.card_progress_logistics.order_scanner", scanner)
        mock.start()
        self.addCleanup(mock.stop)

    def query(self, biz_body: dict):
        return asyncio.run(query_card_progress_logistics(make_request(biz_body)))

    def test_empty_biz_body_returns_empty_biz_body(self) -> None:
        response = self.query({})

        self.assertIsInstance(
            response.transaction.body.response.bizBody,
            EmptyBizBody,
        )
        self.assertEqual(
            response.transaction.header.sysHeader.bizResCd,
            BizResCode.SUCCESS,
        )

    def test_filters_by_exact_file_name(self) -> None:
        response = self.query(
            {
                "page": 1,
                "limit": 10,
                "cardfilename": "8547-newcard-000001-005-20260911",
                "startdate": "20260901",
                "enddate": "20261030",
            }
        )
        result = response.transaction.body.response.bizBody

        self.assertIsInstance(result, CardProgressLogisticsResult)
        self.assertEqual(result.count, 1)
        self.assertEqual(len(result.records), 1)

    def test_paginates_and_sorts_by_order_date_descending(self) -> None:
        response = self.query({"page": 2, "limit": 10})
        result = response.transaction.body.response.bizBody

        self.assertIsInstance(result, CardProgressLogisticsResult)
        self.assertEqual(result.count, 7)
        self.assertEqual(len(result.records), 0)
        dates = [record.orderDate for record in result.records]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_more_than_90_days_returns_business_error(self) -> None:
        response = self.query(
            {
                "page": 1,
                "limit": 10,
                "startdate": "20260101",
                "enddate": "20260601",
            }
        )

        self.assertIsInstance(
            response.transaction.body.response.bizBody,
            EmptyBizBody,
        )
        self.assertEqual(
            response.transaction.header.sysHeader.bizResCd,
            BizResCode.TIME_SPAN_ERROR,
        )

    def test_invalid_business_value_returns_business_error(self) -> None:
        response = self.query(
            {
                "page": 1,
                "limit": 10,
                "cardbiztype": "invalid",
            }
        )

        header = response.transaction.header.sysHeader
        self.assertEqual(header.bizResCd, BizResCode.REQUEST_LOGIC_ERROR)
        self.assertEqual(
            header.resText,
            "cardbiztype must be newcard or changecard",
        )

    def test_invalid_real_date_returns_business_error(self) -> None:
        response = self.query(
            {
                "page": 1,
                "limit": 10,
                "startdate": "20260230",
            }
        )

        header = response.transaction.header.sysHeader
        self.assertEqual(header.bizResCd, BizResCode.REQUEST_LOGIC_ERROR)
        self.assertEqual(
            header.resText,
            "startdate must be a valid date in yyyyMMdd format",
        )

    def test_missing_or_too_long_field_still_fails_model_validation(self) -> None:
        with self.assertRaises(ValidationError):
            make_request({"limit": 10})

        with self.assertRaises(ValidationError):
            make_request(
                {
                    "page": 1,
                    "limit": 10,
                    "startdate": "202601011",
                }
            )

    def test_optional_dates_accept_empty_blank_and_null(self) -> None:
        for value in ("", "   ", None):
            request = make_request(
                {
                    "page": 1,
                    "limit": 10,
                    "startdate": value,
                    "enddate": value,
                }
            )
            response = asyncio.run(query_card_progress_logistics(request))
            self.assertIsInstance(
                response.transaction.body.response.bizBody,
                CardProgressLogisticsResult,
            )

    def test_request_integer_fields_do_not_convert_strings(self) -> None:
        with self.assertRaises(ValidationError):
            make_request({"page": "1", "limit": 10})

        with self.assertRaises(ValidationError):
            SocialCardFeedbackQueryBizBody.model_validate(
                {"page": 1, "limit": "10"}
            )

        with self.assertRaises(ValidationError):
            CardOrderFileTransBizBody.model_validate(
                {
                    "orderDate": "20260812",
                    "orderId": "ORDER-001",
                    "branchCode": "3417837279",
                    "coreFileName": "core.dat",
                    "cardFileName": "card.dat",
                    "cardBizType": "newcard",
                    "cardNum": "100",
                    "productId": "P001",
                    "address": "测试地址",
                    "recipientName": "测试人员",
                    "recipientTel": "01012345678",
                    "recipientPhone": "13800138000",
                }
            )


if __name__ == "__main__":
    unittest.main()
