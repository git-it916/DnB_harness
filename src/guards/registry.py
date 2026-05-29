"""Guard Registry — apply_guards orchestration + summary.

3조건 실험:
    GuardConfig(False, False, False)  → ②번 모드 (가드 OFF)
    GuardConfig(True, True, True)     → ③번 모드 (가드 풀)
"""

from __future__ import annotations

from typing import Callable

from src.guards.base import GuardContext, GuardDecision, GuardEvent
from src.guards.g1_format import check_format
from src.guards.g2_citation import check_citations
from src.guards.g3_constraint import check_constraints
from src.schemas.extraction import ExtractionResult


def apply_guards(
    *,
    raw_extraction_json: str,
    ctx: GuardContext,
    retry_callback: Callable[[str], str] | None = None,
) -> tuple[ExtractionResult | None, list[GuardEvent]]:
    """G1 → G2 → G3 순으로 적용. config 의 토글에 따라 스킵.

    Args:
        raw_extraction_json: LLM 이 만든 raw JSON 문자열
        ctx: GuardContext (config 포함)
        retry_callback: G1 재시도 시 LLM 재호출하는 콜백 (없으면 G1 단발)

    Returns:
        (extraction | None, events)
    """
    events: list[GuardEvent] = []
    extraction: ExtractionResult | None = None

    # G1
    if ctx.config.g1_format:
        extraction, g1_events = check_format(
            raw_extraction_json,
            ExtractionResult,
            retry_callback=retry_callback,
            config=ctx.config,
        )
        events.extend(g1_events)
        if extraction is None:
            return None, events
    else:
        # 가드 OFF: 형식 검증 안 하지만 파싱은 함 (없으면 후속 가드 불가)
        try:
            extraction = ExtractionResult.model_validate_json(raw_extraction_json)
        except Exception as e:
            events.append(
                GuardEvent(
                    guard="G1",
                    field_path=None,
                    decision=GuardDecision.REJECT,
                    reason_code="schema_violation_force",
                    reason=f"가드 OFF 상태에서 파싱 실패: {e}",
                    metadata={"forced": True},
                )
            )
            return None, events

    # G2
    if ctx.config.g2_citation:
        extraction, g2_events = check_citations(extraction, ctx)
        events.extend(g2_events)

    # G3
    if ctx.config.g3_constraint:
        extraction, g3_events = check_constraints(extraction, ctx)
        events.extend(g3_events)

    return extraction, events


def summarize_events(events: list[GuardEvent]) -> dict:
    """guard_log.json 의 summary 블록 생성."""
    by_guard: dict[str, dict[str, int]] = {}
    for ev in events:
        b = by_guard.setdefault(ev.guard, {"pass": 0, "reject": 0, "retry": 0})
        b[ev.decision.value] = b.get(ev.decision.value, 0) + 1

    total = len(events)
    rejected = sum(1 for ev in events if ev.decision == GuardDecision.REJECT)
    return {
        "total_events": total,
        "rejected_count": rejected,
        "by_guard": by_guard,
    }
