from __future__ import annotations

from datetime import date
from typing import Iterable

from src.canonical.compare import compare_values
from src.canonical.parsers import parse_date, parse_duration_months
from src.canonical.policy import load_field_policies
from src.canonical.types import CanonicalComparison, CanonicalValue, FieldPolicy
from src.pipelines.cross_check import (
    CrossCheckResult,
    CrossCheckStatus,
    CrossCheckValue,
    FIELD_LABELS,
    FinalCheckStatus,
    MissingSide,
)
from src.schemas.extraction import ComparableField, ExtractionResult


def cross_check_with_policy(extraction: ExtractionResult) -> list[CrossCheckResult]:
    policies = load_field_policies()
    return [
        _compare_field_with_policy(field_path, field, policies[field_path], extraction)
        for field_path, field in _iter_comparable_fields(extraction)
    ]


def _compare_field_with_policy(
    field_path: str,
    field: ComparableField,
    policy: FieldPolicy,
    extraction: ExtractionResult,
) -> CrossCheckResult:
    missing_side = _missing_side(field)
    if missing_side != MissingSide.NONE:
        return _result_from_missing(field_path, field, missing_side)

    if _canonical_text(field.contract.raw_text) == _canonical_text(field.im.raw_text):
        return CrossCheckResult(
            field=field_path,
            label=FIELD_LABELS[field_path],
            status=CrossCheckStatus.EXACT_MATCH,
            missing_side=MissingSide.NONE,
            final_status=FinalCheckStatus.EXACT_MATCH,
            final_reason_code="raw_text_exact_match",
            final_reason="Raw text matches exactly after whitespace normalization.",
            contract=CrossCheckValue(
                raw_text=field.contract.raw_text,
                citation=field.contract.citation,
            ),
            im=CrossCheckValue(
                raw_text=field.im.raw_text,
                citation=field.im.citation,
            ),
        )

    comparison = _compare_with_derivation(field_path, policy, field, extraction)
    return CrossCheckResult(
        field=field_path,
        label=FIELD_LABELS[field_path],
        status=CrossCheckStatus.NEEDS_REVIEW,
        missing_side=MissingSide.NONE,
        final_status=FinalCheckStatus(comparison.final_status),
        final_reason_code=comparison.reason_code,
        final_reason=comparison.reason,
        canonical_status=comparison.status,
        canonical_reason_code=comparison.reason_code,
        canonical={
            "contract": comparison.contract.model_dump(mode="json"),
            "im": comparison.im.model_dump(mode="json"),
            "judge_allowed": comparison.judge_allowed,
        },
        contract=CrossCheckValue(
            raw_text=field.contract.raw_text,
            citation=field.contract.citation,
        ),
        im=CrossCheckValue(
            raw_text=field.im.raw_text,
            citation=field.im.citation,
        ),
    )


def _compare_with_derivation(
    field_path: str,
    policy: FieldPolicy,
    field: ComparableField,
    extraction: ExtractionResult,
) -> CanonicalComparison:
    if field_path != "fund.maturity_date":
        return compare_values(field_path, policy, field.contract.raw_text, field.im.raw_text)
    contract = _canonical_maturity(
        field.contract.raw_text,
        extraction.fund.inception_date.contract.raw_text,
    )
    im = _canonical_maturity(
        field.im.raw_text,
        extraction.fund.inception_date.im.raw_text,
    )
    return _comparison_from_values(policy, contract, im)


def _canonical_maturity(raw: str | None, inception_raw: str | None) -> CanonicalValue:
    direct = parse_date(raw)
    if direct.status == "decisive":
        return direct
    if raw is None:
        return direct
    compact = raw.replace(" ", "")
    if "설정일" not in compact and "최초설정일" not in compact:
        return CanonicalValue(
            status="non_decisive",
            reason_code="maturity_duration_without_reference",
            reason="Maturity duration does not explicitly reference inception date.",
        )
    inception = parse_date(inception_raw)
    duration = parse_duration_months(raw)
    if inception.status != "decisive" or duration.status != "decisive":
        return CanonicalValue(
            status="non_decisive",
            reason_code="maturity_derivation_failed",
            reason="Maturity derivation requires decisive inception date and duration.",
        )
    derived = _add_months(date.fromisoformat(inception.value), int(duration.value))
    return CanonicalValue(
        status="decisive",
        value=derived.isoformat(),
        unit="date",
        method="derived_from_inception",
        reason_code="maturity_derived_from_inception",
        reason="Maturity date derived from same-side inception date.",
        metadata={"inception_date": inception.value, "duration_months": duration.value},
    )


def _comparison_from_values(
    policy: FieldPolicy,
    contract: CanonicalValue,
    im: CanonicalValue,
) -> CanonicalComparison:
    if contract.status != "decisive" or im.status != "decisive":
        return CanonicalComparison(
            status="non_decisive",
            final_status=str(FinalCheckStatus.NEEDS_REVIEW),
            reason_code="canonical_not_decisive",
            reason="One or both sides could not be canonicalized decisively.",
            contract=contract,
            im=im,
            judge_allowed=policy.judge_allowed,
        )
    if contract.unit == im.unit and contract.value == im.value:
        return CanonicalComparison(
            status="decisive",
            final_status=str(FinalCheckStatus.SAME_AFTER_NORMALIZATION),
            reason_code="canonical_date_equal",
            reason="Canonical dates are equal under field policy.",
            contract=contract,
            im=im,
            judge_allowed=policy.judge_allowed,
        )
    return CanonicalComparison(
        status="decisive",
        final_status=str(FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION),
        reason_code="canonical_date_difference",
        reason="Canonical dates differ under field policy.",
        contract=contract,
        im=im,
        judge_allowed=policy.judge_allowed,
    )


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, _last_day_of_month(year, month))
    return date(year, month, day)


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _result_from_missing(
    field_path: str,
    field: ComparableField,
    missing_side: MissingSide,
) -> CrossCheckResult:
    return CrossCheckResult(
        field=field_path,
        label=FIELD_LABELS[field_path],
        status=CrossCheckStatus.MISSING_EVIDENCE,
        missing_side=missing_side,
        final_status=FinalCheckStatus.MISSING_EVIDENCE,
        final_reason_code="missing_evidence",
        final_reason="One or both sides are missing raw evidence.",
        contract=CrossCheckValue(
            raw_text=field.contract.raw_text,
            citation=field.contract.citation,
        ),
        im=CrossCheckValue(
            raw_text=field.im.raw_text,
            citation=field.im.citation,
        ),
    )


def _missing_side(field: ComparableField) -> MissingSide:
    contract_missing = field.contract.raw_text is None
    im_missing = field.im.raw_text is None
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
