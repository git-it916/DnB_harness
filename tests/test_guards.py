from pathlib import Path

from src.guards.base import GuardConfig, GuardContext, GuardDecision
from src.guards.g3_constraint import check_constraints
from src.schemas.extraction import ExtractionResult


def test_g3_shacl_delegation_emits_reject_event_when_enabled():
    extraction, events = check_constraints(
        _high_management_fee_extraction(),
        GuardContext(
            contract_pdf=Path("contract.pdf"),
            im_pdf=Path("im.pdf"),
            contract_pages=22,
            im_pages=24,
            config=GuardConfig(g3_use_shacl=True),
        ),
    )

    assert extraction is not None
    assert any(
        event.guard == "G3"
        and event.decision == GuardDecision.REJECT
        and event.reason_code == "shacl_violation"
        for event in events
    )


def _high_management_fee_extraction() -> ExtractionResult:
    return ExtractionResult.model_validate(
        {
            "schema_version": "v0",
            "fund": {
                "name": _pair("이지스 블랙ON 일반사모투자신탁제1호", "이지스 블랙ON 일반사모투자신탁제1호"),
                "type": _missing_pair(),
                "inception_date": _missing_pair(),
                "maturity_date": _missing_pair(),
            },
            "party": {
                "asset_manager": _pair("집합투자업자: 이지스자산운용", "운용회사: 이지스자산운용"),
                "trustee": _pair("신탁업자: 국민은행", "수탁회사: 국민은행"),
                "distributor": _missing_pair(),
            },
            "fee_schedule": {
                "management_fee": _pair("집합투자업자보수율 : 연 1,000분의 8.9", "[운용] 연[ 8.9 ] %"),
                "trust_fee": _missing_pair(),
                "sales_fee": _missing_pair(),
            },
            "redemption_terms": {
                "is_redeemable": _missing_pair(),
                "lockup_period": _missing_pair(),
                "redemption_cycle": _missing_pair(),
                "redemption_fee": _missing_pair(),
            },
        }
    )


def _pair(contract_raw_text: str, im_raw_text: str):
    return {
        "contract": {
            "value": None,
            "unit": None,
            "raw_text": contract_raw_text,
            "citation": {"document": "신탁계약서", "page": 1},
        },
        "im": {
            "value": None,
            "unit": None,
            "raw_text": im_raw_text,
            "citation": {"document": "IM", "page": 1},
        },
    }


def _missing_pair():
    missing = {"value": None, "unit": None, "raw_text": None, "citation": None}
    return {"contract": missing, "im": missing}
