"""G2 출처 가드 — citation.page 가 실제 PDF 페이지 범위 안인지 결정론적으로 확인.

가짜 인용(예: 골든셋 C029의 page=999)을 잡아내고, 해당 필드 한쪽을 null로 만든다.
"""

from __future__ import annotations

from typing import Literal

from src.guards.base import (
    GuardContext,
    GuardDecision,
    GuardEvent,
    iter_comparable_fields,
    nullify_side,
)
from src.schemas.extraction import ComparableField, DocumentValue, ExtractionResult


def check_citations(
    extraction: ExtractionResult, ctx: GuardContext
) -> tuple[ExtractionResult, list[GuardEvent]]:
    """모든 14필드의 contract/im citation 페이지를 검증."""
    events: list[GuardEvent] = []
    current = extraction

    for field_path, comparable in iter_comparable_fields(extraction):
        for side in ("contract", "im"):
            event = _check_one_side(field_path, comparable, side, ctx)
            if event is None:
                continue
            events.append(event)
            if event.decision == GuardDecision.REJECT:
                current = nullify_side(current, field_path, side)
    return current, events


def _check_one_side(
    field_path: str,
    comparable: ComparableField,
    side: Literal["contract", "im"],
    ctx: GuardContext,
) -> GuardEvent | None:
    doc_value: DocumentValue = getattr(comparable, side)
    if doc_value.citation is None:
        return None  # raw_text 없으면 검증 대상 아님

    max_page = ctx.contract_pages if side == "contract" else ctx.im_pages
    page = doc_value.citation.page
    field_id = f"{field_path}.{side}"

    if not (1 <= page <= max_page):
        return GuardEvent(
            guard="G2",
            field_path=field_id,
            decision=GuardDecision.REJECT,
            reason_code="page_out_of_range",
            reason=f"page {page} ∉ [1, {max_page}]",
            metadata={"page": page, "max_page": max_page, "side": side},
        )

    # citation.document 와 side 일치 여부도 검사
    expected_doc = "신탁계약서" if side == "contract" else "IM"
    if doc_value.citation.document != expected_doc:
        return GuardEvent(
            guard="G2",
            field_path=field_id,
            decision=GuardDecision.REJECT,
            reason_code="citation_document_mismatch",
            reason=f"side={side} 이지만 citation.document={doc_value.citation.document}",
            metadata={"expected": expected_doc, "actual": doc_value.citation.document, "side": side},
        )

    return GuardEvent(
        guard="G2",
        field_path=field_id,
        decision=GuardDecision.PASS,
        reason_code="page_in_range",
        reason=f"page {page} ∈ [1, {max_page}]",
        metadata={"page": page, "max_page": max_page, "side": side},
    )
