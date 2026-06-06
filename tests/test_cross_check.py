from src.pipelines.cross_check import (
    CrossCheckResult,
    CrossCheckStatus,
    CrossCheckValue,
    FinalCheckStatus,
    MissingSide,
    cross_check_extraction,
    apply_normalization_to_cross_check,
    judge_inputs_from_results,
)
from src.pipelines.normalize import NormalizationResult, NormalizationStatus
from src.schemas.extraction import ExtractionResult


def test_cross_check_returns_all_w1_fields():
    results = cross_check_extraction(_sample_extraction())

    assert len(results) == 14
    assert {result.field for result in results} == {
        "fund.name",
        "fund.type",
        "fund.inception_date",
        "fund.maturity_date",
        "party.asset_manager",
        "party.trustee",
        "party.distributor",
        "fee_schedule.management_fee",
        "fee_schedule.trust_fee",
        "fee_schedule.sales_fee",
        "redemption_terms.is_redeemable",
        "redemption_terms.lockup_period",
        "redemption_terms.redemption_cycle",
        "redemption_terms.redemption_fee",
    }


def test_cross_check_treats_whitespace_only_difference_as_exact_match():
    result = _result_by_field(cross_check_extraction(_sample_extraction()), "fund.name")

    assert result.status == CrossCheckStatus.EXACT_MATCH
    assert result.missing_side == MissingSide.NONE


def test_cross_check_marks_different_raw_text_as_needs_review():
    result = _result_by_field(
        cross_check_extraction(_sample_extraction()),
        "fee_schedule.management_fee",
    )

    assert result.status == CrossCheckStatus.NEEDS_REVIEW
    assert result.missing_side == MissingSide.NONE
    assert result.contract.raw_text == "운용보수는 연 0.7%로 한다"
    assert result.im.raw_text == "운용보수 연 0.7%"
    assert result.final_status == FinalCheckStatus.NEEDS_REVIEW


def test_cross_check_marks_missing_side():
    results = cross_check_extraction(_sample_extraction())

    assert _result_by_field(results, "party.distributor").missing_side == MissingSide.IM
    assert _result_by_field(results, "fee_schedule.sales_fee").missing_side == MissingSide.BOTH


def test_judge_inputs_are_created_only_for_needs_review_results():
    judge_inputs = judge_inputs_from_results(cross_check_extraction(_sample_extraction()))

    assert {judge_input.field for judge_input in judge_inputs} == {
        "fee_schedule.management_fee",
        "redemption_terms.redemption_cycle",
    }
    management_fee = next(
        item for item in judge_inputs if item.field == "fee_schedule.management_fee"
    )
    assert management_fee.label == "운용보수"
    assert management_fee.contract_raw_text == "운용보수는 연 0.7%로 한다"
    assert management_fee.im_raw_text == "운용보수 연 0.7%"


def test_judge_inputs_skip_results_resolved_by_normalization():
    results = cross_check_extraction(_sample_extraction())
    merged = apply_normalization_to_cross_check(
        results,
        [
            _normalization_result(
                field="fee_schedule.management_fee",
                status=NormalizationStatus.SAME,
                reason_code="same_normalized_value",
            )
        ],
    )

    judge_inputs = judge_inputs_from_results(merged)

    assert {judge_input.field for judge_input in judge_inputs} == {
        "redemption_terms.redemption_cycle"
    }


def test_apply_normalization_to_cross_check_marks_normalized_match():
    results = cross_check_extraction(_sample_extraction())
    normalization_results = [
        _normalization_result(
            field="fee_schedule.management_fee",
            status=NormalizationStatus.SAME,
            reason_code="same_normalized_value",
        )
    ]

    merged = apply_normalization_to_cross_check(results, normalization_results)
    result = _result_by_field(merged, "fee_schedule.management_fee")

    assert result.status == CrossCheckStatus.NEEDS_REVIEW
    assert result.normalization_status == "same_after_normalization"
    assert result.final_status == FinalCheckStatus.SAME_AFTER_NORMALIZATION
    assert result.final_reason_code == "same_normalized_value"


def test_apply_normalization_to_cross_check_marks_normalized_difference():
    results = cross_check_extraction(_sample_extraction())
    normalization_results = [
        _normalization_result(
            field="fee_schedule.management_fee",
            status=NormalizationStatus.DIFFERENT,
            reason_code="different_normalized_value",
        )
    ]

    result = _result_by_field(
        apply_normalization_to_cross_check(results, normalization_results),
        "fee_schedule.management_fee",
    )

    assert result.final_status == FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION
    assert result.final_reason_code == "different_normalized_value"


def test_apply_normalization_to_cross_check_keeps_missing_evidence_final_status():
    results = cross_check_extraction(_sample_extraction())
    normalization_results = [
        _normalization_result(
            field="party.distributor",
            status=NormalizationStatus.SAME,
            reason_code="same_normalized_value",
        )
    ]

    result = _result_by_field(
        apply_normalization_to_cross_check(results, normalization_results),
        "party.distributor",
    )

    assert result.status == CrossCheckStatus.MISSING_EVIDENCE
    assert result.final_status == FinalCheckStatus.MISSING_EVIDENCE
    assert result.normalization_status == "same_after_normalization"


def test_cross_check_result_accepts_optional_canonical_metadata():
    result = CrossCheckResult(
        field="fee_schedule.sales_fee",
        label="판매보수",
        status=CrossCheckStatus.NEEDS_REVIEW,
        missing_side=MissingSide.NONE,
        final_status=FinalCheckStatus.SAME_AFTER_NORMALIZATION,
        final_reason_code="canonical_numeric_equal",
        final_reason="Canonical values are equal after explicit unit conversion.",
        canonical_status="decisive",
        canonical_reason_code="numeric_equal_after_unit_conversion",
        canonical={
            "contract": {"value": "0.3", "unit": "percent_per_year"},
            "im": {"value": "0.3", "unit": "percent_per_year"},
        },
        contract=CrossCheckValue(raw_text="연 1,000분의 3", citation=None),
        im=CrossCheckValue(raw_text="연 0.3%", citation=None),
    )

    dumped = result.model_dump()
    assert dumped["canonical_status"] == "decisive"
    assert dumped["canonical"]["contract"]["value"] == "0.3"


def _result_by_field(results, field):
    return next(result for result in results if result.field == field)


def _sample_extraction() -> ExtractionResult:
    missing = {"value": None, "unit": None, "raw_text": None, "citation": None}

    payload = {
        "schema_version": "v0",
        "fund": {
            "name": _pair(
                "이지스 블랙ON 일반사모투자신탁제1호",
                "이지스 블랙ON\n일반사모투자신탁제1호",
            ),
            "type": _pair("일반사모투자신탁", "일반사모투자신탁"),
            "inception_date": _pair("설정일은 2024년 5월 31일", "설정일은 2024년 5월 31일"),
            "maturity_date": _pair("만기일은 2029년 5월 31일", "만기일은 2029년 5월 31일"),
        },
        "party": {
            "asset_manager": _pair("집합투자업자: 이지스자산운용", "집합투자업자: 이지스자산운용"),
            "trustee": _pair("신탁업자: 국민은행", "신탁업자: 국민은행"),
            "distributor": {
                "contract": {
                    "value": None,
                    "unit": None,
                    "raw_text": "판매회사: 하나증권",
                    "citation": {"document": "신탁계약서", "page": 1},
                },
                "im": missing,
            },
        },
        "fee_schedule": {
            "management_fee": _pair("운용보수는 연 0.7%로 한다", "운용보수 연 0.7%"),
            "trust_fee": _pair("신탁보수는 연 0.03%로 한다", "신탁보수는 연 0.03%로 한다"),
            "sales_fee": {"contract": missing, "im": missing},
        },
        "redemption_terms": {
            "is_redeemable": _pair("수익자는 환매를 청구할 수 있다", "수익자는 환매를 청구할 수 있다"),
            "lockup_period": _pair("설정일로부터 1년간 환매 제한", "설정일로부터 1년간 환매 제한"),
            "redemption_cycle": _pair("매월 15일 환매청구 가능", "월 1회 환매 가능"),
            "redemption_fee": _pair("환매수수료 없음", "환매수수료 없음"),
        },
    }

    return ExtractionResult.model_validate(payload)


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


def _normalization_result(
    *, field: str, status: NormalizationStatus, reason_code: str
) -> NormalizationResult:
    return NormalizationResult(
        field=field,
        label="운용보수",
        status=status,
        reason_code=reason_code,
        reason="Normalization comparison result.",
        contract={
            "raw_text": "contract raw",
            "normalized_text": "0.7",
            "normalized_value": 0.7,
            "normalized_unit": "percent_per_year",
            "method": "direct",
            "reason_code": "normalized_successfully",
            "reason": "Normalized.",
        },
        im={
            "raw_text": "im raw",
            "normalized_text": "0.7",
            "normalized_value": 0.7,
            "normalized_unit": "percent_per_year",
            "method": "direct",
            "reason_code": "normalized_successfully",
            "reason": "Normalized.",
        },
    )
