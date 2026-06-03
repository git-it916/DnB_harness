"""G3 제약 가드 — 결정론 범위/논리 검증.

(a) 필드별 범위: 보수 0~5%, 날짜 포맷 등
(b) 교차 논리: 만기일 > 설정일
(c) SHACL 위임 (config.g3_use_shacl=True 일 때)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from src.guards.base import (
    GuardContext,
    GuardDecision,
    GuardEvent,
    iter_comparable_fields,
    nullify_side,
)
from src.ontology.mapping import extraction_to_graph
from src.ontology.validate import validate_graph
from src.schemas.extraction import ComparableField, DocumentValue, ExtractionResult

# 결정론 범위 규칙
PERCENT_RANGES = {
    "fee_schedule.management_fee": (0.0, 5.0),
    "fee_schedule.trust_fee": (0.0, 2.0),
    "fee_schedule.sales_fee": (0.0, 3.0),
}

ISO_DATE_FIELDS = {"fund.inception_date", "fund.maturity_date"}

_PERCENT_PATTERN = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%")
_PERMILLE_PATTERN = re.compile(r"1[,，]?000\s*분의\s*([0-9]+(?:\.[0-9]+)?)")


def check_constraints(
    extraction: ExtractionResult, ctx: GuardContext
) -> tuple[ExtractionResult, list[GuardEvent]]:
    """범위 + 교차 논리 검증. 위반 시 해당 측 null화."""
    events: list[GuardEvent] = []
    current = extraction

    # (a) 필드별 범위
    for field_path, comparable in iter_comparable_fields(extraction):
        for side in ("contract", "im"):
            event = _check_field_range(field_path, comparable, side)
            if event is None:
                continue
            events.append(event)
            if event.decision == GuardDecision.REJECT:
                current = nullify_side(current, field_path, side)

    # (b) 교차 논리: 만기일 > 설정일 (per side)
    for side in ("contract", "im"):
        event = _check_maturity_after_inception(current, side)
        if event is not None:
            events.append(event)
            if event.decision == GuardDecision.REJECT:
                # 만기일 null 처리 (덜 신뢰 가는 쪽)
                current = nullify_side(current, "fund.maturity_date", side)

    # (c) SHACL 위임: ontology 조건의 진단을 guard 조건에서 집행 신호로 연결
    if ctx.config.g3_use_shacl:
        event = _check_shacl_constraints(current)
        if event is not None:
            events.append(event)

    return current, events


def _check_field_range(
    field_path: str, comparable: ComparableField, side: Literal["contract", "im"]
) -> GuardEvent | None:
    doc_value: DocumentValue = getattr(comparable, side)
    if doc_value.raw_text is None:
        return None

    field_id = f"{field_path}.{side}"

    # 보수 범위 (% 단위로 정규화 후 검사)
    if field_path in PERCENT_RANGES:
        min_v, max_v = PERCENT_RANGES[field_path]
        pct = _to_percent(doc_value.raw_text)
        if pct is None:
            # 인식 못 한 단위 — pass 처리 (정규화 단계에서 다룸)
            return GuardEvent(
                guard="G3",
                field_path=field_id,
                decision=GuardDecision.PASS,
                reason_code="unit_not_recognized",
                reason="단위 정규화 불가 — 범위 검증 스킵",
                metadata={"raw_text": doc_value.raw_text},
            )
        if not (min_v <= pct <= max_v):
            return GuardEvent(
                guard="G3",
                field_path=field_id,
                decision=GuardDecision.REJECT,
                reason_code="percent_range",
                reason=f"{pct}% ∉ [{min_v}, {max_v}]",
                metadata={"value_pct": pct, "min": min_v, "max": max_v, "raw_text": doc_value.raw_text},
            )
        return GuardEvent(
            guard="G3",
            field_path=field_id,
            decision=GuardDecision.PASS,
            reason_code="percent_in_range",
            reason=f"{pct}% ∈ [{min_v}, {max_v}]",
            metadata={"value_pct": pct},
        )

    # 날짜 포맷 (느슨)
    if field_path in ISO_DATE_FIELDS:
        d = _try_parse_date(doc_value.raw_text)
        if d is None:
            return GuardEvent(
                guard="G3",
                field_path=field_id,
                decision=GuardDecision.PASS,
                reason_code="date_unparseable",
                reason="날짜 표기 인식 불가 — 검증 스킵",
                metadata={"raw_text": doc_value.raw_text},
            )
        return GuardEvent(
            guard="G3",
            field_path=field_id,
            decision=GuardDecision.PASS,
            reason_code="date_parsed",
            reason=f"parsed={d.isoformat()}",
            metadata={"date": d.isoformat()},
        )

    return None  # 기타 필드는 G3 검증 대상 아님


def _check_maturity_after_inception(
    extraction: ExtractionResult, side: Literal["contract", "im"]
) -> GuardEvent | None:
    incept_dv: DocumentValue = getattr(extraction.fund.inception_date, side)
    maturity_dv: DocumentValue = getattr(extraction.fund.maturity_date, side)
    if incept_dv.raw_text is None or maturity_dv.raw_text is None:
        return None

    incept = _try_parse_date(incept_dv.raw_text)
    maturity = _try_parse_date(maturity_dv.raw_text)
    if incept is None or maturity is None:
        return None  # 검증 불가

    field_id = f"fund.maturity_date.{side}"
    if maturity <= incept:
        return GuardEvent(
            guard="G3",
            field_path=field_id,
            decision=GuardDecision.REJECT,
            reason_code="maturity_not_after_inception",
            reason=f"만기={maturity.isoformat()} ≤ 설정일={incept.isoformat()}",
            metadata={
                "inception": incept.isoformat(),
                "maturity": maturity.isoformat(),
                "side": side,
            },
        )
    return GuardEvent(
        guard="G3",
        field_path=field_id,
        decision=GuardDecision.PASS,
        reason_code="maturity_after_inception",
        reason=f"만기={maturity.isoformat()} > 설정일={incept.isoformat()}",
        metadata={"inception": incept.isoformat(), "maturity": maturity.isoformat()},
    )


def _check_shacl_constraints(extraction: ExtractionResult) -> GuardEvent | None:
    graph = extraction_to_graph(extraction)
    result = validate_graph(graph)
    if result.conforms:
        return GuardEvent(
            guard="G3",
            field_path=None,
            decision=GuardDecision.PASS,
            reason_code="shacl_conforms",
            reason="SHACL validation conforms",
            metadata={},
        )

    return GuardEvent(
        guard="G3",
        field_path=None,
        decision=GuardDecision.REJECT,
        reason_code="shacl_violation",
        reason="SHACL validation failed",
        metadata={"report_text": result.report_text},
    )


# ---- helpers ----

def _to_percent(raw: str) -> float | None:
    """raw text → 백분율(%) 값. 인식 못 하면 None."""
    s = raw.replace("，", ",")
    # 1) "연 0.89 %" / "[운용] 연[ 8.9 ] %" → 0.89 / 8.9
    #    대괄호·소괄호를 공백으로 치환해 표 형식(IM)도 파싱.
    s_percent = re.sub(r"[\[\]()]", " ", s)
    m = _PERCENT_PATTERN.search(s_percent)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    # 2) "1,000분의 8.9" → 0.89  (콤마 보존 위해 원본 s 사용)
    m = _PERMILLE_PATTERN.search(s)
    if m:
        try:
            return float(m.group(1)) / 10.0
        except ValueError:
            pass
    return None


def _try_parse_date(raw: str) -> datetime | None:
    """느슨한 한국어/ISO 날짜 파싱."""
    s = raw.strip()
    # ISO
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt)
        except ValueError:
            continue
    # 한글 "2025년 7월 22일"
    m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", s)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime(y, mo, d)
        except ValueError:
            return None
    return None
