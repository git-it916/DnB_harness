import json
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from src.client.anthropic_client import AnthropicJSONClient
from src.pipelines.cross_check import (
    CrossCheckResult,
    CrossCheckStatus,
    JudgeInput,
    judge_inputs_from_results,
)


DEFAULT_JUDGE_PROMPT_PATH = Path("prompts/v0/judge/system.md")


class JudgeStatus(StrEnum):
    SAME = "same"
    DIFFERENT = "different"


class JudgeLLM(Protocol):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        ...


class StrictJudgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMJudgement(StrictJudgeModel):
    field: str
    reason: str
    status: JudgeStatus

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be empty")
        return value


def judge_needs_review(
    cross_check_results: list[CrossCheckResult],
    *,
    llm: JudgeLLM | None = None,
    system_prompt_path: Path = DEFAULT_JUDGE_PROMPT_PATH,
) -> list[LLMJudgement]:
    judge_inputs = judge_inputs_from_results(cross_check_results)
    if not judge_inputs:
        return []

    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    judge_llm = llm or AnthropicJSONClient()

    judgements = []
    for judge_input in judge_inputs:
        payload = judge_llm.complete_json(
            system_prompt=system_prompt,
            user_prompt=judge_prompt_for_input(judge_input),
        )
        judgement = LLMJudgement.model_validate(payload)
        if judgement.field != judge_input.field:
            raise ValueError(
                f"field mismatch: expected {judge_input.field}, got {judgement.field}"
            )
        judgements.append(judgement)
    return judgements


def judge_prompt_for_input(judge_input: JudgeInput) -> str:
    payload = {
        "field": judge_input.field,
        "label": judge_input.label,
        "contract_raw_text": judge_input.contract_raw_text,
        "im_raw_text": judge_input.im_raw_text,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def needs_judge(result: CrossCheckResult) -> bool:
    return result.status == CrossCheckStatus.NEEDS_REVIEW
