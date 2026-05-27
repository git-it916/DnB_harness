import pytest
from pydantic import ValidationError

from src.schemas.extraction import (
    Citation,
    DocumentValue,
    ExtractionResult,
)


def test_document_value_requires_citation_when_raw_text_exists():
    with pytest.raises(ValidationError, match="citation is required"):
        DocumentValue(
            value="0.7",
            unit="percent_per_year",
            raw_text="운용보수는 연 0.7%로 한다",
            citation=None,
        )


def test_document_value_allows_missing_value_when_all_evidence_is_null():
    missing = DocumentValue(value=None, unit=None, raw_text=None, citation=None)

    assert missing.raw_text is None
    assert missing.citation is None


def test_citation_document_is_limited_to_w1_documents():
    with pytest.raises(ValidationError):
        Citation(document="핵심상품설명서", page=1)


def test_citation_page_is_one_based():
    with pytest.raises(ValidationError):
        Citation(document="신탁계약서", page=0)


def test_extraction_result_requires_all_w1_sections_and_fields():
    payload = {
        "schema_version": "v0",
        "fund": {
            "name": {
                "contract": {
                    "value": "이지스 블랙ON 일반사모투자신탁제1호",
                    "unit": "fund_name",
                    "raw_text": "이지스 블랙ON 일반사모투자신탁제1호",
                    "citation": {"document": "신탁계약서", "page": 1},
                },
                "im": {
                    "value": "이지스 블랙ON 일반사모투자신탁제1호",
                    "unit": "fund_name",
                    "raw_text": "이지스 블랙ON 일반사모투자신탁제1호",
                    "citation": {"document": "IM", "page": 1},
                },
            },
            "type": _missing_pair(),
            "inception_date": _missing_pair(),
            "maturity_date": _missing_pair(),
        },
        "party": {
            "asset_manager": _missing_pair(),
            "trustee": _missing_pair(),
            "distributor": _missing_pair(),
        },
        "fee_schedule": {
            "management_fee": _missing_pair(),
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

    result = ExtractionResult.model_validate(payload)

    assert result.schema_version == "v0"
    assert result.fund.name.contract.citation.document == "신탁계약서"
    assert result.fund.name.im.citation.document == "IM"


def test_extraction_result_rejects_missing_w1_field():
    payload = {
        "schema_version": "v0",
        "fund": {
            "name": _missing_pair(),
            "type": _missing_pair(),
            "inception_date": _missing_pair(),
        },
        "party": {
            "asset_manager": _missing_pair(),
            "trustee": _missing_pair(),
            "distributor": _missing_pair(),
        },
        "fee_schedule": {
            "management_fee": _missing_pair(),
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

    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(payload)


def _missing_pair():
    missing = {"value": None, "unit": None, "raw_text": None, "citation": None}
    return {"contract": missing, "im": missing}
