"""Guard 공통 인터페이스: GuardEvent, GuardConfig, GuardContext, helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from src.schemas.extraction import ComparableField, DocumentValue, ExtractionResult


class GuardDecision(StrEnum):
    PASS = "pass"
    REJECT = "reject"
    RETRY = "retry"


class GuardEvent(BaseModel):
    """가드 1회 결과. guard_log.json 의 events[] 원소."""
    model_config = ConfigDict(extra="forbid")

    guard: Literal["G1", "G2", "G3"]
    field_path: str | None
    decision: GuardDecision
    reason_code: str
    reason: str
    metadata: dict[str, Any] = {}


@dataclass(frozen=True)
class GuardConfig:
    """3조건 실험의 가드 ON/OFF + 옵션."""
    g1_format: bool = True
    g2_citation: bool = True
    g3_constraint: bool = True
    g1_max_retries: int = 1
    g3_use_shacl: bool = False  # MVP에선 결정론 규칙만


@dataclass(frozen=True)
class GuardContext:
    """가드 실행에 필요한 외부 정보."""
    contract_pdf: Path
    im_pdf: Path
    contract_pages: int
    im_pages: int
    config: GuardConfig = GuardConfig()


@runtime_checkable
class Guard(Protocol):
    name: str

    def check(
        self, extraction: ExtractionResult, ctx: GuardContext
    ) -> tuple[ExtractionResult, list[GuardEvent]]: ...


# ---- 공용 helpers ----

FIELD_PATHS: list[str] = [
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
]


def iter_comparable_fields(
    extraction: ExtractionResult,
) -> Iterable[tuple[str, ComparableField]]:
    """ExtractionResult 의 14 필드를 (path, ComparableField) 로 순회."""
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


def nullify_side(
    extraction: ExtractionResult, field_path: str, side: Literal["contract", "im"]
) -> ExtractionResult:
    """field_path 의 한쪽(side)을 null DocumentValue로 교체한 새 ExtractionResult.

    Pydantic 불변 보장: model_copy(deep=True) + update.
    """
    null_value = DocumentValue(value=None, unit=None, raw_text=None, citation=None)
    extraction = extraction.model_copy(deep=True)
    section, sub = field_path.split(".", 1)
    section_obj = getattr(extraction, section)
    field_obj: ComparableField = getattr(section_obj, sub)
    setattr(field_obj, side, null_value)
    return extraction


def strip_markdown_fence(text: str) -> str:
    """```json ... ``` 같은 fence 제거."""
    s = text.strip()
    if s.startswith("```"):
        # remove first line (e.g. ```json) and trailing fence
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s
