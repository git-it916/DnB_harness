from enum import StrEnum
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, model_validator

from src.schemas.extraction import Citation, ComparableField, DocumentValue, ExtractionResult


class CrossCheckStatus(StrEnum):
    EXACT_MATCH = "exact_match"
    NEEDS_REVIEW = "needs_review"
    MISSING_EVIDENCE = "missing_evidence"


class FinalCheckStatus(StrEnum):
    EXACT_MATCH = "exact_match"
    SAME_AFTER_NORMALIZATION = "same_after_normalization"
    DIFFERENT_AFTER_NORMALIZATION = "different_after_normalization"
    NEEDS_REVIEW = "needs_review"
    MISSING_EVIDENCE = "missing_evidence"


class MissingSide(StrEnum):
    CONTRACT = "contract"
    IM = "im"
    BOTH = "both"
    NONE = "none"


class StrictResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CrossCheckValue(StrictResultModel):
    raw_text: str | None
    citation: Citation | None


class CrossCheckResult(StrictResultModel):
    field: str
    label: str
    status: CrossCheckStatus
    missing_side: MissingSide
    normalization_status: str | None = None
    final_status: FinalCheckStatus | None = None
    final_reason_code: str | None = None
    final_reason: str | None = None
    contract: CrossCheckValue
    im: CrossCheckValue

    @model_validator(mode="after")
    def default_final_result(self) -> "CrossCheckResult":
        if (
            self.final_status is not None
            and self.final_reason_code is not None
            and self.final_reason is not None
        ):
            return self
        final_status, final_reason_code, final_reason = _default_final_result(self.status)
        self.final_status = self.final_status or final_status
        self.final_reason_code = self.final_reason_code or final_reason_code
        self.final_reason = self.final_reason or final_reason
        return self


class JudgeInput(StrictResultModel):
    field: str
    label: str
    contract_raw_text: str
    im_raw_text: str


FIELD_LABELS = {
    "fund.name": "펀드명",
    "fund.type": "펀드 유형",
    "fund.inception_date": "설정일",
    "fund.maturity_date": "만기일",
    "party.asset_manager": "운용사",
    "party.trustee": "신탁업자",
    "party.distributor": "판매사",
    "fee_schedule.management_fee": "운용보수",
    "fee_schedule.trust_fee": "신탁보수",
    "fee_schedule.sales_fee": "판매보수",
    "redemption_terms.is_redeemable": "환매 가능 여부",
    "redemption_terms.lockup_period": "락업 기간",
    "redemption_terms.redemption_cycle": "환매 주기",
    "redemption_terms.redemption_fee": "환매수수료",
}


def cross_check_extraction(extraction: ExtractionResult) -> list[CrossCheckResult]:
    return [
        _compare_field(field_path, field)
        for field_path, field in _iter_comparable_fields(extraction)
    ]


def apply_normalization_to_cross_check(
    cross_check_results: Iterable[CrossCheckResult],
    normalization_results: Iterable[Any],
) -> list[CrossCheckResult]:
    normalization_by_field = {
        result.field: result for result in normalization_results
    }
    return [
        _apply_normalization_result(result, normalization_by_field.get(result.field))
        for result in cross_check_results
    ]


def judge_inputs_from_results(results: Iterable[CrossCheckResult]) -> list[JudgeInput]:
    judge_inputs = []
    for result in results:
        if result.status != CrossCheckStatus.NEEDS_REVIEW:
            continue
        if result.final_status != FinalCheckStatus.NEEDS_REVIEW:
            continue
        if result.contract.raw_text is None or result.im.raw_text is None:
            continue
        judge_inputs.append(
            JudgeInput(
                field=result.field,
                label=result.label,
                contract_raw_text=result.contract.raw_text,
                im_raw_text=result.im.raw_text,
            )
        )
    return judge_inputs


def _compare_field(field_path: str, field: ComparableField) -> CrossCheckResult:
    missing_side = _missing_side(field.contract, field.im)
    if missing_side != MissingSide.NONE:
        status = CrossCheckStatus.MISSING_EVIDENCE
    elif _canonical_text(field.contract.raw_text) == _canonical_text(field.im.raw_text):
        status = CrossCheckStatus.EXACT_MATCH
    else:
        status = CrossCheckStatus.NEEDS_REVIEW
    final_status, final_reason_code, final_reason = _default_final_result(status)

    return CrossCheckResult(
        field=field_path,
        label=FIELD_LABELS[field_path],
        status=status,
        missing_side=missing_side,
        final_status=final_status,
        final_reason_code=final_reason_code,
        final_reason=final_reason,
        contract=CrossCheckValue(
            raw_text=field.contract.raw_text,
            citation=field.contract.citation,
        ),
        im=CrossCheckValue(
            raw_text=field.im.raw_text,
            citation=field.im.citation,
        ),
    )


def _apply_normalization_result(
    result: CrossCheckResult, normalization_result: Any | None
) -> CrossCheckResult:
    if normalization_result is None:
        return result

    normalization_status = str(normalization_result.status)
    if result.status == CrossCheckStatus.MISSING_EVIDENCE:
        final_status = FinalCheckStatus.MISSING_EVIDENCE
        final_reason_code = "missing_evidence"
        final_reason = "Raw evidence is missing, so normalization cannot override the raw cross-check result."
    elif result.status == CrossCheckStatus.EXACT_MATCH:
        final_status = FinalCheckStatus.EXACT_MATCH
        final_reason_code = "raw_text_exact_match"
        final_reason = "Raw text matches exactly after whitespace normalization."
    elif normalization_status == FinalCheckStatus.SAME_AFTER_NORMALIZATION:
        final_status = FinalCheckStatus.SAME_AFTER_NORMALIZATION
        final_reason_code = str(normalization_result.reason_code)
        final_reason = str(normalization_result.reason)
    elif normalization_status == FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION:
        final_status = FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION
        final_reason_code = str(normalization_result.reason_code)
        final_reason = str(normalization_result.reason)
    else:
        final_status = FinalCheckStatus.NEEDS_REVIEW
        final_reason_code = "normalization_not_decisive"
        final_reason = "Normalization did not produce a decisive same or different result."

    return result.model_copy(
        update={
            "normalization_status": normalization_status,
            "final_status": final_status,
            "final_reason_code": final_reason_code,
            "final_reason": final_reason,
        }
    )


def _default_final_result(
    status: CrossCheckStatus,
) -> tuple[FinalCheckStatus, str, str]:
    if status == CrossCheckStatus.EXACT_MATCH:
        return (
            FinalCheckStatus.EXACT_MATCH,
            "raw_text_exact_match",
            "Raw text matches exactly after whitespace normalization.",
        )
    if status == CrossCheckStatus.MISSING_EVIDENCE:
        return (
            FinalCheckStatus.MISSING_EVIDENCE,
            "missing_evidence",
            "One or both sides are missing raw evidence.",
        )
    return (
        FinalCheckStatus.NEEDS_REVIEW,
        "raw_text_difference",
        "Raw text differs and no decisive normalization result has been applied.",
    )


def _missing_side(contract: DocumentValue, im: DocumentValue) -> MissingSide:
    contract_missing = contract.raw_text is None
    im_missing = im.raw_text is None
    if contract_missing and im_missing:
        return MissingSide.BOTH
    if contract_missing:
        return MissingSide.CONTRACT
    if im_missing:
        return MissingSide.IM
    return MissingSide.NONE


def _canonical_text(raw_text: str | None) -> str | None:
    if raw_text is None:
        return None
    return " ".join(raw_text.split())


def _iter_comparable_fields(
    extraction: ExtractionResult,
) -> Iterable[tuple[str, ComparableField]]:
    yield "fund.name", extraction.fund.name
    yield "fund.type", extraction.fund.type
    yield "fund.inception_date", extraction.fund.inception_date
    yield "fund.maturity_date", extraction.fund.maturity_date
    yield "party.asset_manager", extraction.party.asset_manager
    yield "party.trustee", extraction.party.trustee
    yield "party.distributor", extraction.party.distributor
    yield "fee_schedule.management_fee", extraction.fee_schedule.management_fee
    yield "fee_schedule.trust_fee", extraction.fee_schedule.trust_fee
    yield "fee_schedule.sales_fee", extraction.fee_schedule.sales_fee
    yield "redemption_terms.is_redeemable", extraction.redemption_terms.is_redeemable
    yield "redemption_terms.lockup_period", extraction.redemption_terms.lockup_period
    yield "redemption_terms.redemption_cycle", extraction.redemption_terms.redemption_cycle
    yield "redemption_terms.redemption_fee", extraction.redemption_terms.redemption_fee
