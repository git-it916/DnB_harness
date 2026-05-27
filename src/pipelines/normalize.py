import json
import re
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from src.client.anthropic_client import AnthropicJSONClient
from src.pipelines.cross_check import FIELD_LABELS
from src.schemas.extraction import ComparableField, DocumentValue, ExtractionResult


DEFAULT_NORMALIZATION_PROMPT_PATH = Path("prompts/v0/normalize/system.md")
FLOAT_TOLERANCE = 0.000001


class NormalizationStatus(StrEnum):
    SAME = "same_after_normalization"
    DIFFERENT = "different_after_normalization"
    PARTIAL = "partially_normalized"
    FAILED = "normalization_failed"
    NOT_NORMALIZED = "not_normalized"


class NormalizationMethod(StrEnum):
    DIRECT = "direct"
    DERIVED_FROM_REFERENCE_DATE = "derived_from_reference_date"
    NOT_NORMALIZED = "not_normalized"


class NormalizationLLM(Protocol):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...


class StrictNormalizationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMNormalizationSide(StrictNormalizationModel):
    normalized_text: str | None
    normalized_unit: str | None
    method: str
    reason_code: str
    reason: str
    raw_normalized_text: str | None = None
    raw_normalized_unit: str | None = None

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be empty")
        return value


class LLMNormalizationResult(StrictNormalizationModel):
    field: str
    contract: LLMNormalizationSide
    im: LLMNormalizationSide


class NormalizationSideResult(StrictNormalizationModel):
    raw_text: str | None
    normalized_text: str | None
    normalized_value: str | float | int | None
    normalized_unit: str | None
    method: NormalizationMethod
    reason_code: str
    reason: str
    raw_normalized_text: str | None = None
    raw_normalized_value: str | float | int | None = None
    raw_normalized_unit: str | None = None
    derived_from: list[str] = []
    reference_date: str | None = None
    reference_date_field: str | None = None
    reference_date_source: str | None = None
    reference_date_policy: str | None = None


class NormalizationResult(StrictNormalizationModel):
    field: str
    label: str
    status: NormalizationStatus
    reason_code: str
    reason: str
    contract: NormalizationSideResult
    im: NormalizationSideResult


class NormalizationInput(StrictNormalizationModel):
    field: str
    target_unit: str
    contract_raw_text: str | None
    im_raw_text: str | None
    reference_date: str | None = None
    reference_date_field: str | None = None
    reference_date_source: str | None = None
    reference_date_policy: str | None = None


NORMALIZATION_TARGETS = {
    "fund.inception_date": "date",
    "fund.maturity_date": "date",
    "fee_schedule.management_fee": "percent_per_year",
    "fee_schedule.trust_fee": "percent_per_year",
    "fee_schedule.sales_fee": "percent_per_year",
}

DERIVED_DATE_FIELDS = {"fund.maturity_date"}


def normalize_extraction(
    extraction: ExtractionResult,
    *,
    llm: NormalizationLLM | None = None,
    system_prompt_path: Path = DEFAULT_NORMALIZATION_PROMPT_PATH,
) -> list[NormalizationResult]:
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    normalization_llm = llm or AnthropicJSONClient()
    results_by_field: dict[str, NormalizationResult] = {}

    for field_path, field in _iter_comparable_fields(extraction):
        result = _normalize_field(
            field_path=field_path,
            field=field,
            results_by_field=results_by_field,
            llm=normalization_llm,
            system_prompt=system_prompt,
        )
        results_by_field[field_path] = result

    return [results_by_field[field_path] for field_path, _ in _iter_comparable_fields(extraction)]


def normalization_prompt_for_input(prompt_input: dict[str, Any] | NormalizationInput) -> str:
    if isinstance(prompt_input, NormalizationInput):
        payload = prompt_input.model_dump(mode="json")
    else:
        payload = prompt_input
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_field(
    *,
    field_path: str,
    field: ComparableField,
    results_by_field: dict[str, NormalizationResult],
    llm: NormalizationLLM,
    system_prompt: str,
) -> NormalizationResult:
    if field_path not in NORMALIZATION_TARGETS:
        return _field_not_in_scope(field_path, field)

    if not _has_evidence(field.contract) and not _has_evidence(field.im):
        return _not_normalized_for_missing_evidence(field_path, field)

    prompt_input = NormalizationInput(
        field=field_path,
        target_unit=NORMALIZATION_TARGETS[field_path],
        contract_raw_text=field.contract.raw_text if _has_evidence(field.contract) else None,
        im_raw_text=field.im.raw_text if _has_evidence(field.im) else None,
        **_reference_date_payload(field_path, results_by_field),
    )
    payload = llm.complete_json(
        system_prompt=system_prompt,
        user_prompt=normalization_prompt_for_input(prompt_input),
    )
    llm_result = LLMNormalizationResult.model_validate(payload)
    if llm_result.field != field_path:
        raise ValueError(f"field mismatch: expected {field_path}, got {llm_result.field}")

    contract = _build_side_result(
        field_path=field_path,
        source="contract",
        document_value=field.contract,
        llm_side=llm_result.contract,
        prompt_input=prompt_input,
    )
    im = _build_side_result(
        field_path=field_path,
        source="im",
        document_value=field.im,
        llm_side=llm_result.im,
        prompt_input=prompt_input,
    )
    status, reason_code, reason = _field_status(contract, im)
    return NormalizationResult(
        field=field_path,
        label=FIELD_LABELS[field_path],
        status=status,
        reason_code=reason_code,
        reason=reason,
        contract=contract,
        im=im,
    )


def _build_side_result(
    *,
    field_path: str,
    source: str,
    document_value: DocumentValue,
    llm_side: LLMNormalizationSide,
    prompt_input: NormalizationInput,
) -> NormalizationSideResult:
    if not _has_evidence(document_value):
        return _side_not_normalized(
            raw_text=document_value.raw_text,
            reason_code="missing_evidence",
            reason="raw_text and citation.page are required before normalization.",
        )

    target_unit = NORMALIZATION_TARGETS[field_path]
    converted_value = _convert_normalized_text(
        llm_side.normalized_text,
        llm_side.normalized_unit,
        target_unit,
    )
    converted_raw_value = _convert_raw_normalized_text(
        llm_side.raw_normalized_text,
        llm_side.raw_normalized_unit,
    )
    method = _valid_method(llm_side.method)
    if converted_value is None or method is None:
        return _side_not_normalized(
            raw_text=document_value.raw_text,
            normalized_text=llm_side.normalized_text,
            normalized_unit=llm_side.normalized_unit,
            raw_normalized_text=llm_side.raw_normalized_text,
            raw_normalized_unit=llm_side.raw_normalized_unit,
            reason_code="normalization_failed",
            reason="The AI normalization output failed unit, method, or type validation.",
        )

    derived = method == NormalizationMethod.DERIVED_FROM_REFERENCE_DATE
    return NormalizationSideResult(
        raw_text=document_value.raw_text,
        normalized_text=llm_side.normalized_text,
        normalized_value=converted_value,
        normalized_unit=llm_side.normalized_unit,
        method=method,
        reason_code=llm_side.reason_code,
        reason=llm_side.reason,
        raw_normalized_text=llm_side.raw_normalized_text if derived else None,
        raw_normalized_value=converted_raw_value if derived else None,
        raw_normalized_unit=llm_side.raw_normalized_unit if derived else None,
        derived_from=["fund.inception_date"] if derived else [],
        reference_date=prompt_input.reference_date if derived else None,
        reference_date_field=prompt_input.reference_date_field if derived else None,
        reference_date_source=prompt_input.reference_date_source if derived else None,
        reference_date_policy=prompt_input.reference_date_policy if derived else None,
    )


def _field_status(
    contract: NormalizationSideResult,
    im: NormalizationSideResult,
) -> tuple[NormalizationStatus, str, str]:
    contract_success = _side_success(contract)
    im_success = _side_success(im)
    if contract_success and im_success:
        if contract.normalized_unit == im.normalized_unit and _values_equal(
            contract.normalized_value,
            im.normalized_value,
            contract.normalized_unit,
        ):
            return (
                NormalizationStatus.SAME,
                "same_normalized_value",
                "Both sides normalize to the same value and unit.",
            )
        return (
            NormalizationStatus.DIFFERENT,
            "different_normalized_value",
            "Both sides normalized successfully, but the values or units differ.",
        )
    if contract_success or im_success:
        return (
            NormalizationStatus.PARTIAL,
            "partial_normalization_success",
            "Only one side normalized successfully.",
        )
    return (
        NormalizationStatus.FAILED,
        "normalization_failed",
        "Both sides have evidence, but neither side normalized successfully.",
    )


def _reference_date_payload(
    field_path: str,
    results_by_field: dict[str, NormalizationResult],
) -> dict[str, str | None]:
    if field_path not in DERIVED_DATE_FIELDS:
        return {
            "reference_date": None,
            "reference_date_field": None,
            "reference_date_source": None,
            "reference_date_policy": None,
        }
    inception = results_by_field.get("fund.inception_date")
    if inception is None:
        return _no_reference_date_payload()

    contract_date = (
        inception.contract.normalized_value
        if _side_success(inception.contract)
        and inception.contract.normalized_unit == "date"
        else None
    )
    im_date = (
        inception.im.normalized_value
        if _side_success(inception.im) and inception.im.normalized_unit == "date"
        else None
    )
    if contract_date is not None and im_date is not None and contract_date == im_date:
        return {
            "reference_date": str(contract_date),
            "reference_date_field": "fund.inception_date",
            "reference_date_source": "both",
            "reference_date_policy": "both_sides_same",
        }
    if contract_date is not None and im_date is None:
        return {
            "reference_date": str(contract_date),
            "reference_date_field": "fund.inception_date",
            "reference_date_source": "contract",
            "reference_date_policy": "single_side_with_evidence:contract",
        }
    if im_date is not None and contract_date is None:
        return {
            "reference_date": str(im_date),
            "reference_date_field": "fund.inception_date",
            "reference_date_source": "im",
            "reference_date_policy": "single_side_with_evidence:im",
        }
    return _no_reference_date_payload()


def _no_reference_date_payload() -> dict[str, str | None]:
    return {
        "reference_date": None,
        "reference_date_field": None,
        "reference_date_source": None,
        "reference_date_policy": "reference_date_missing",
    }


def _field_not_in_scope(field_path: str, field: ComparableField) -> NormalizationResult:
    reason = "The field is outside W1 normalization scope."
    return NormalizationResult(
        field=field_path,
        label=FIELD_LABELS[field_path],
        status=NormalizationStatus.NOT_NORMALIZED,
        reason_code="field_not_in_scope",
        reason=reason,
        contract=_side_not_normalized(
            raw_text=field.contract.raw_text,
            reason_code="field_not_in_scope",
            reason=reason,
        ),
        im=_side_not_normalized(
            raw_text=field.im.raw_text,
            reason_code="field_not_in_scope",
            reason=reason,
        ),
    )


def _not_normalized_for_missing_evidence(
    field_path: str, field: ComparableField
) -> NormalizationResult:
    reason = "Neither side has raw_text with citation.page."
    return NormalizationResult(
        field=field_path,
        label=FIELD_LABELS[field_path],
        status=NormalizationStatus.NOT_NORMALIZED,
        reason_code="missing_evidence",
        reason=reason,
        contract=_side_not_normalized(
            raw_text=field.contract.raw_text,
            reason_code="missing_evidence",
            reason=reason,
        ),
        im=_side_not_normalized(
            raw_text=field.im.raw_text,
            reason_code="missing_evidence",
            reason=reason,
        ),
    )


def _side_not_normalized(
    *,
    raw_text: str | None,
    reason_code: str,
    reason: str,
    normalized_text: str | None = None,
    normalized_unit: str | None = None,
    raw_normalized_text: str | None = None,
    raw_normalized_unit: str | None = None,
) -> NormalizationSideResult:
    return NormalizationSideResult(
        raw_text=raw_text,
        normalized_text=normalized_text,
        normalized_value=None,
        normalized_unit=normalized_unit,
        method=NormalizationMethod.NOT_NORMALIZED,
        reason_code=reason_code,
        reason=reason,
        raw_normalized_text=raw_normalized_text,
        raw_normalized_value=None,
        raw_normalized_unit=raw_normalized_unit,
    )


def _convert_normalized_text(
    normalized_text: str | None,
    normalized_unit: str | None,
    expected_unit: str,
) -> str | float | int | None:
    if normalized_text is None or normalized_unit != expected_unit:
        return None
    if expected_unit == "percent_per_year":
        return _parse_number(normalized_text)
    if expected_unit == "date":
        return _parse_iso_date(normalized_text)
    if expected_unit == "month":
        return _parse_int(normalized_text)
    return None


def _convert_raw_normalized_text(
    raw_normalized_text: str | None,
    raw_normalized_unit: str | None,
) -> str | float | int | None:
    if raw_normalized_text is None and raw_normalized_unit is None:
        return None
    if raw_normalized_unit == "month":
        return _parse_int(raw_normalized_text)
    return None


def _parse_number(value: str | None) -> float | None:
    if value is None or not re.fullmatch(r"-?\d+(?:\.\d+)?", value.strip()):
        return None
    return float(value)


def _parse_int(value: str | None) -> int | None:
    if value is None or not re.fullmatch(r"-?\d+", value.strip()):
        return None
    return int(value)


def _parse_iso_date(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    try:
        parsed = date.fromisoformat(stripped)
    except ValueError:
        return None
    return parsed.isoformat()


def _valid_method(method: str) -> NormalizationMethod | None:
    try:
        return NormalizationMethod(method)
    except ValueError:
        return None


def _side_success(side: NormalizationSideResult) -> bool:
    return side.normalized_value is not None and side.normalized_unit is not None


def _values_equal(
    left: str | float | int | None,
    right: str | float | int | None,
    unit: str | None,
) -> bool:
    if unit == "percent_per_year" and isinstance(left, (int, float)) and isinstance(
        right, (int, float)
    ):
        return abs(float(left) - float(right)) <= FLOAT_TOLERANCE
    return left == right


def _has_evidence(document_value: DocumentValue) -> bool:
    return document_value.raw_text is not None and document_value.citation is not None


def _iter_comparable_fields(
    extraction: ExtractionResult,
) -> Iterable[tuple[str, ComparableField]]:
    yield "fund.inception_date", extraction.fund.inception_date
    yield "fund.maturity_date", extraction.fund.maturity_date
    yield "fee_schedule.management_fee", extraction.fee_schedule.management_fee
    yield "fee_schedule.trust_fee", extraction.fee_schedule.trust_fee
    yield "fee_schedule.sales_fee", extraction.fee_schedule.sales_fee
    yield "fund.name", extraction.fund.name
    yield "fund.type", extraction.fund.type
    yield "party.asset_manager", extraction.party.asset_manager
    yield "party.trustee", extraction.party.trustee
    yield "party.distributor", extraction.party.distributor
    yield "redemption_terms.is_redeemable", extraction.redemption_terms.is_redeemable
    yield "redemption_terms.lockup_period", extraction.redemption_terms.lockup_period
    yield "redemption_terms.redemption_cycle", extraction.redemption_terms.redemption_cycle
    yield "redemption_terms.redemption_fee", extraction.redemption_terms.redemption_fee
