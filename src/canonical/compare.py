from __future__ import annotations

from src.canonical.parsers import parse_boolean, parse_date, parse_duration_months, parse_percent
from src.canonical.types import CanonicalComparison, CanonicalValue, FieldPolicy
from src.pipelines.cross_check import FinalCheckStatus


def compare_values(
    field: str,
    policy: FieldPolicy,
    contract_raw: str | None,
    im_raw: str | None,
) -> CanonicalComparison:
    contract = canonicalize_value(field, policy, contract_raw)
    im = canonicalize_value(field, policy, im_raw)

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

    same = contract.unit == im.unit and contract.value == im.value
    if same:
        return CanonicalComparison(
            status="decisive",
            final_status=str(FinalCheckStatus.SAME_AFTER_NORMALIZATION),
            reason_code=_same_reason(policy.compare_policy),
            reason="Canonical values are equal under field policy.",
            contract=contract,
            im=im,
            judge_allowed=policy.judge_allowed,
        )
    return CanonicalComparison(
        status="decisive",
        final_status=str(FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION),
        reason_code=_different_reason(policy.compare_policy),
        reason="Canonical values differ under field policy.",
        contract=contract,
        im=im,
        judge_allowed=policy.judge_allowed,
    )


def canonicalize_value(field: str, policy: FieldPolicy, raw: str | None) -> CanonicalValue:
    absence = canonicalize_absence(policy, raw)
    if absence is not None:
        return absence
    if policy.canonicalizer == "percent":
        return parse_percent(raw)
    if policy.canonicalizer == "date":
        return parse_date(raw)
    if policy.canonicalizer == "duration":
        return parse_duration_months(raw)
    if policy.canonicalizer == "boolean":
        return parse_boolean(raw)
    return CanonicalValue(
        status="non_decisive",
        reason_code="canonicalizer_not_configured",
        reason=f"No deterministic canonicalizer is configured for {field}.",
    )


def canonicalize_absence(policy: FieldPolicy, raw: str | None) -> CanonicalValue | None:
    if raw is None:
        return CanonicalValue(
            status="non_decisive",
            reason_code="missing_raw_text",
            reason="Raw text is missing.",
        )
    text = raw.strip()
    if not text:
        return CanonicalValue(
            status="non_decisive",
            reason_code="missing_raw_text",
            reason="Raw text is empty.",
        )
    compact = text.replace(" ", "")
    absence_tokens = ("없음", "해당없음", "해당사항없음", "부과하지아니함", "면제")
    if not any(token in compact for token in absence_tokens):
        return None
    if policy.absence_semantics == "zero_value":
        return CanonicalValue(
            status="decisive",
            value="0",
            unit=policy.value_type,
            method="absence_zero",
            reason_code="absence_as_zero",
            reason="Absence expression is configured as zero value for this field.",
        )
    return CanonicalValue(
        status="non_decisive",
        reason_code="absence_as_missing",
        reason="Absence expression is configured as missing evidence for this field.",
    )


def _same_reason(compare_policy: str) -> str:
    if compare_policy == "numeric_equal":
        return "canonical_numeric_equal"
    if compare_policy == "date_equal":
        return "canonical_date_equal"
    if compare_policy == "duration_equal":
        return "canonical_duration_equal"
    if compare_policy == "boolean_equal":
        return "canonical_boolean_equal"
    return "canonical_equal"


def _different_reason(compare_policy: str) -> str:
    if compare_policy == "numeric_equal":
        return "canonical_numeric_difference"
    if compare_policy == "date_equal":
        return "canonical_date_difference"
    if compare_policy == "duration_equal":
        return "canonical_duration_difference"
    if compare_policy == "boolean_equal":
        return "canonical_boolean_difference"
    return "canonical_difference"
