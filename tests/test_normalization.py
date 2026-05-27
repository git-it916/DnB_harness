import json

import pytest
from pydantic import ValidationError

from src.pipelines.normalize import (
    NormalizationStatus,
    normalize_extraction,
    normalization_prompt_for_input,
)
from src.schemas.extraction import ExtractionResult


def test_normalize_extraction_returns_all_fields_and_computes_statuses():
    llm = FakeNormalizationLLM(
        [
            {
                "field": "fund.inception_date",
                "contract": _side("2025-07-22", "date"),
                "im": _side("2025-07-22", "date"),
            },
            {
                "field": "fund.maturity_date",
                "contract": _side("2027-07-22", "date"),
                "im": {
                    "normalized_text": "2027-07-22",
                    "normalized_unit": "date",
                    "raw_normalized_text": "24",
                    "raw_normalized_unit": "month",
                    "method": "derived_from_reference_date",
                    "reason_code": "derived_successfully",
                    "reason": "The 2-year term was converted using the reference date.",
                },
            },
            {
                "field": "fee_schedule.management_fee",
                "contract": _side("0.89", "percent_per_year"),
                "im": _side("0.8900001", "percent_per_year"),
            },
            {
                "field": "fee_schedule.trust_fee",
                "contract": _side("0.05", "percent_per_year"),
                "im": _side("0.05", "percent_per_year"),
            },
            {
                "field": "fee_schedule.sales_fee",
                "contract": _side("0.03", "percent_per_year"),
                "im": _side("0.04", "percent_per_year"),
            },
        ]
    )

    results = normalize_extraction(_extraction_for_normalization(), llm=llm)

    assert len(results) == 14
    by_field = {result.field: result for result in results}
    assert by_field["fund.inception_date"].status == NormalizationStatus.SAME
    assert by_field["fund.inception_date"].contract.normalized_value == "2025-07-22"
    assert by_field["fund.maturity_date"].status == NormalizationStatus.SAME
    assert by_field["fund.maturity_date"].im.raw_normalized_value == 24
    assert by_field["fund.maturity_date"].im.reference_date_source == "both"
    assert by_field["fee_schedule.management_fee"].status == NormalizationStatus.SAME
    assert by_field["fee_schedule.management_fee"].im.normalized_value == pytest.approx(
        0.8900001
    )
    assert by_field["fee_schedule.sales_fee"].status == NormalizationStatus.DIFFERENT
    assert by_field["party.asset_manager"].status == NormalizationStatus.NOT_NORMALIZED
    assert by_field["party.asset_manager"].reason_code == "field_not_in_scope"
    assert [prompt["field"] for prompt in llm.prompts] == [
        "fund.inception_date",
        "fund.maturity_date",
        "fee_schedule.management_fee",
        "fee_schedule.trust_fee",
        "fee_schedule.sales_fee",
    ]
    assert llm.prompts[1]["reference_date"] == "2025-07-22"
    assert llm.prompts[1]["reference_date_policy"] == "both_sides_same"


def test_normalize_extraction_marks_missing_target_field_without_llm_call():
    llm = FakeNormalizationLLM([])
    extraction = _extraction_for_normalization(missing_target_fields=True)

    results = normalize_extraction(extraction, llm=llm)

    by_field = {result.field: result for result in results}
    assert by_field["fund.inception_date"].status == NormalizationStatus.NOT_NORMALIZED
    assert by_field["fund.inception_date"].reason_code == "missing_evidence"
    assert llm.prompts == []


def test_normalize_extraction_rejects_unit_outside_field_scope():
    llm = FakeNormalizationLLM(
        [
            {
                "field": "fund.inception_date",
                "contract": _side("2025-07-22", "date"),
                "im": _side("2025-07-22", "date"),
            },
            {
                "field": "fund.maturity_date",
                "contract": _side("2027-07-22", "date"),
                "im": _side("2027-07-22", "date"),
            },
            {
                "field": "fee_schedule.management_fee",
                "contract": _side("0.89", "percent"),
                "im": _side("0.89", "percent_per_year"),
            },
            {
                "field": "fee_schedule.trust_fee",
                "contract": _side("0.05", "percent_per_year"),
                "im": _side("0.05", "percent_per_year"),
            },
            {
                "field": "fee_schedule.sales_fee",
                "contract": _side("0.03", "percent_per_year"),
                "im": _side("0.03", "percent_per_year"),
            },
        ]
    )

    results = normalize_extraction(_extraction_for_normalization(), llm=llm)

    management_fee = {result.field: result for result in results}[
        "fee_schedule.management_fee"
    ]
    assert management_fee.status == NormalizationStatus.PARTIAL
    assert management_fee.contract.normalized_value is None
    assert management_fee.contract.reason_code == "normalization_failed"


def test_normalization_prompt_uses_raw_text_and_omits_citation_and_extracted_value():
    prompt = normalization_prompt_for_input(
        {
            "field": "fee_schedule.management_fee",
            "target_unit": "percent_per_year",
            "contract_raw_text": "집합투자업자보수율 : 연 1,000 분의 8.9",
            "im_raw_text": "[운용] 연[ 0.89 ] %",
            "reference_date": None,
            "reference_date_field": None,
            "reference_date_source": None,
            "reference_date_policy": None,
        }
    )

    payload = json.loads(prompt)
    assert payload["field"] == "fee_schedule.management_fee"
    assert payload["contract_raw_text"] == "집합투자업자보수율 : 연 1,000 분의 8.9"
    assert "citation" not in prompt
    assert "page" not in prompt
    assert "value" not in prompt


def test_normalize_extraction_rejects_wrong_field_from_llm():
    llm = FakeNormalizationLLM(
        [
            {
                "field": "fund.maturity_date",
                "contract": _side("2025-07-22", "date"),
                "im": _side("2025-07-22", "date"),
            }
        ]
    )

    with pytest.raises(ValueError, match="field mismatch"):
        normalize_extraction(_extraction_for_normalization(), llm=llm)


def test_normalize_extraction_rejects_missing_reason_from_llm():
    llm = FakeNormalizationLLM(
        [
            {
                "field": "fund.inception_date",
                "contract": {
                    "normalized_text": "2025-07-22",
                    "normalized_unit": "date",
                    "method": "direct",
                    "reason_code": "normalized_successfully",
                    "reason": "",
                },
                "im": _side("2025-07-22", "date"),
            }
        ]
    )

    with pytest.raises(ValidationError):
        normalize_extraction(_extraction_for_normalization(), llm=llm)


class FakeNormalizationLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def complete_json(self, *, system_prompt: str, user_prompt: str):
        self.prompts.append(json.loads(user_prompt))
        return self.responses.pop(0)


def _side(normalized_text: str, normalized_unit: str) -> dict:
    return {
        "normalized_text": normalized_text,
        "normalized_unit": normalized_unit,
        "method": "direct",
        "reason_code": "normalized_successfully",
        "reason": "The raw text was normalized directly.",
    }


def _extraction_for_normalization(
    *, missing_target_fields: bool = False
) -> ExtractionResult:
    missing = {"value": None, "unit": None, "raw_text": None, "citation": None}

    def found(document: str, page: int, raw_text: str) -> dict:
        return {
            "value": "llm candidate not used",
            "unit": "llm_unit_not_used",
            "raw_text": raw_text,
            "citation": {"document": document, "page": page},
        }

    def pair(contract_raw: str, im_raw: str) -> dict:
        return {
            "contract": found("신탁계약서", 1, contract_raw),
            "im": found("IM", 1, im_raw),
        }

    target_pair = {"contract": missing, "im": missing} if missing_target_fields else None
    return ExtractionResult.model_validate(
        {
            "schema_version": "v0",
            "fund": {
                "name": pair("펀드명", "펀드명"),
                "type": pair("투자신탁", "투자신탁"),
                "inception_date": target_pair
                or pair("2025 년 7 월 22 일부터 시행한다.", "2025년7월22일"),
                "maturity_date": target_pair
                or pair("2027 년 7 월 22 일까지로 한다.", "펀드만기 2년"),
            },
            "party": {
                "asset_manager": pair("이지스자산운용", "이지스자산운용"),
                "trustee": pair("엔에이치투자증권", "엔에이치투자증권"),
                "distributor": {"contract": missing, "im": missing},
            },
            "fee_schedule": {
                "management_fee": target_pair
                or pair("연 1,000 분의 8.9", "연[ 0.89 ] %"),
                "trust_fee": target_pair or pair("연 1,000 분의 0.5", "연[ 0.05] %"),
                "sales_fee": target_pair or pair("연 1,000 분의 0.3", "연[ 0.03 ] %"),
            },
            "redemption_terms": {
                "is_redeemable": pair("환매를 청구할 수 없다", "환매 불가능"),
                "lockup_period": {"contract": missing, "im": missing},
                "redemption_cycle": {"contract": missing, "im": missing},
                "redemption_fee": pair("해당사항 없음", "환매 불가"),
            },
        }
    )
