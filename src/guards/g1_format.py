"""G1 형식 가드 — Pydantic 검증 + 1회 재시도."""

from __future__ import annotations

import json
from typing import Callable

from pydantic import BaseModel, ValidationError

from src.guards.base import GuardConfig, GuardDecision, GuardEvent, strip_markdown_fence


def check_format(
    raw_output: str,
    schema: type[BaseModel],
    *,
    retry_callback: Callable[[str], str] | None = None,
    config: GuardConfig = GuardConfig(),
) -> tuple[BaseModel | None, list[GuardEvent]]:
    """raw LLM 출력을 schema 로 검증. 실패하면 (max_retries 만큼) 재시도.

    Returns:
        (parsed_instance | None, events)
    """
    events: list[GuardEvent] = []
    attempts = 1 + config.g1_max_retries

    last_error: str = ""
    last_output = raw_output

    for attempt in range(1, attempts + 1):
        cleaned = strip_markdown_fence(last_output)
        try:
            instance = schema.model_validate_json(cleaned)
            events.append(
                GuardEvent(
                    guard="G1",
                    field_path=None,
                    decision=GuardDecision.PASS,
                    reason_code="json_valid" if attempt == 1 else "json_valid_after_retry",
                    reason=f"Pydantic 검증 통과 (attempt={attempt})",
                    metadata={"attempt": attempt},
                )
            )
            return instance, events
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            events.append(
                GuardEvent(
                    guard="G1",
                    field_path=None,
                    decision=GuardDecision.RETRY if attempt < attempts else GuardDecision.REJECT,
                    reason_code="schema_violation",
                    reason=last_error[:300],
                    metadata={"attempt": attempt},
                )
            )
            if attempt < attempts and retry_callback is not None:
                last_output = retry_callback(
                    f"이전 응답이 스키마 검증 실패했습니다. 오류: {last_error[:300]}\n"
                    f"수정해서 JSON 만 답하세요."
                )
            else:
                break

    return None, events
