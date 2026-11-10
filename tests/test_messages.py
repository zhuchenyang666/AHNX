import inspect
import json

from pydantic import BaseModel

import app.models as public_models
import app.models.esb as esb_models
import app.models.card_progress_logistics as card_progress_logistics_models
import app.models.social_card_feedback as social_card_feedback_models
from app.models import (
    CardProgressLogisticsRequest,
    CardProgressLogisticsResponse,
    SocialCardFeedbackRequest,
    SocialCardFeedbackResponse,
)


def request_message(biz_body: dict, service_code: str, transaction_code: str) -> dict:
    return {
        "Transaction": {
            "Body": {"request": {"bizBody": biz_body}},
            "Header": {
                "sysHeader": {
                    "servCd": service_code,
                    "globalSq": "02920260815010000000282001000000",
                    "rqstDate": "2026-08-15",
                    "rqstTime": "12:08:05.321",
                    "rqstSysCd": "029",
                    "prvdSysCd": "662",
                    "tranCode": transaction_code,
                }
            },
        }
    }


def response_message(biz_body: dict, service_code: str, transaction_code: str) -> dict:
    result = request_message(biz_body, service_code, transaction_code)
    transaction = result["Transaction"]
    transaction["Body"] = {"response": {"bizBody": biz_body}}
    transaction["Header"]["sysHeader"].update(
        {
            "prvdDate": "2026-08-15",
            "prvdTime": "12:08:05.400",
            "bizResCd": "AAAAAAA",
            "bizResText": "交易成功",
        }
    )
    return result


def assert_round_trip(model: type[BaseModel], raw: dict) -> None:
    message = model.from_json(json.dumps(raw, ensure_ascii=False))
    assert model.from_json(message.to_json()) == message


def test_card_progress_logistics_messages_round_trip() -> None:
    assert_round_trip(
        CardProgressLogisticsRequest,
        request_message(
            {"page": 1, "limit": 10, "branchcode": "3417837279"},
            "3033000315",
            "ICCARD12001001",
        ),
    )
    assert_round_trip(
        CardProgressLogisticsResponse,
        response_message({"count": 0, "records": []}, "3033000315", "ICCARD12001001"),
    )


def test_social_card_feedback_messages_round_trip() -> None:
    assert_round_trip(
        SocialCardFeedbackRequest,
        request_message(
            {"page": 1, "limit": 10, "blnginstid": "3417837279"},
            "3033000314",
            "ICCARD12001002",
        ),
    )
    assert_round_trip(
        SocialCardFeedbackResponse,
        response_message({"count": 0, "records": []}, "3033000314", "ICCARD12001002"),
    )


def test_public_model_api_has_no_protected_names() -> None:
    assert all(not name.startswith("_") for name in public_models.__all__)


def test_every_model_field_has_description_and_alias() -> None:
    modules = [
        esb_models,
        card_progress_logistics_models,
        social_card_feedback_models,
    ]
    model_classes = []
    for module in modules:
        model_classes.extend(
            value
            for _, value in inspect.getmembers(module, inspect.isclass)
            if issubclass(value, BaseModel) and value.__module__ == module.__name__
        )
    assert model_classes
    for model in model_classes:
        invalid = [
            name
            for name, field in model.model_fields.items()
            if not field.description or not field.alias
        ]
        assert not invalid, f"{model.__name__} invalid fields: {invalid}"


def test_python_field_names_and_json_aliases_follow_protocol() -> None:
    request_fields = card_progress_logistics_models.CardProgressLogisticsQueryBizBody.model_fields
    assert request_fields["branchCode"].alias == "branchcode"
    assert request_fields["cardFileName"].alias == "cardfilename"
    assert request_fields["cardBizType"].alias == "cardbiztype"
    assert request_fields["startDate"].alias == "startdate"
    assert request_fields["endDate"].alias == "enddate"

    record_fields = card_progress_logistics_models.CardProgressLogisticsRecordBizBody.model_fields
    assert record_fields["orderDate"].alias == "orderdate"
    assert record_fields["cardFileName"].alias == "cardfilename"
    assert record_fields["logisticsCompany"].alias == "logisticscompany"

    social_fields = social_card_feedback_models.SocialCardFeedbackRecordBizBody.model_fields
    assert social_fields["blngInstId"].alias == "blnginstid"
    assert social_fields["socInsFileBtcNum"].alias == "socinsfilebtcnum"
    assert social_fields["crdPrdDt"].alias == "crdprddt"

    transaction_fields = esb_models.RequestTransaction.model_fields
    assert transaction_fields["body"].alias == "Body"
    assert transaction_fields["header"].alias == "Header"
    assert esb_models.EsbRequest.model_fields["transaction"].alias == "Transaction"
