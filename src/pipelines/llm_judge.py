import json
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from typing import Literal

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


class RedeemabilityJudgement(StrictJudgeModel):
    field: Literal["redemption_terms.is_redeemable"]
    contract_redeemable: Literal["yes", "no", "conditional", "unknown"]
    im_redeemable: Literal["yes", "no", "conditional", "unknown"]
    confidence: Literal["high", "medium", "low"]
    reason_code: str
    contract_evidence: str
    im_evidence: str
    reason: str

    @field_validator("reason", "reason_code", "contract_evidence", "im_evidence")
    @classmethod
    def text_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text fields must not be empty")
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


_REDEEMABILITY_SYSTEM_PROMPT = """\
You classify redeemability for Korean private fund documents.

Return JSON only with these fields:
- field: must be "redemption_terms.is_redeemable"
- contract_redeemable: "yes" | "no" | "conditional" | "unknown"
- im_redeemable: "yes" | "no" | "conditional" | "unknown"
- confidence: "high" | "medium" | "low"
- reason_code: short snake_case code
- contract_evidence: short phrase from contract text supporting the class
- im_evidence: short phrase from IM text supporting the class
- reason: one short Korean explanation

Classify each side independently:
- "yes": redemption is allowed.
- "no": redemption is not allowed, including closed-ended fund or no redemption before maturity.
- "conditional": redemption depends on special conditions, exceptions, gates, approval, or partial restrictions.
- "unknown": evidence is insufficient or ambiguous.

Do not decide same/different directly. Do not use outside knowledge.
Use high confidence only when both side classifications are explicit from the given text.
"""


def judge_redeemability(
    result: CrossCheckResult,
    *,
    llm: JudgeLLM | None = None,
) -> RedeemabilityJudgement:
    if result.field != "redemption_terms.is_redeemable":
        raise ValueError(f"redeemability judge cannot handle field: {result.field}")
    judge_llm = llm or AnthropicJSONClient()
    payload = judge_llm.complete_json(
        system_prompt=_REDEEMABILITY_SYSTEM_PROMPT,
        user_prompt=json.dumps(
            {
                "field": result.field,
                "label": result.label,
                "contract_raw_text": result.contract.raw_text,
                "im_raw_text": result.im.raw_text,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    return RedeemabilityJudgement.model_validate(payload)


def resolve_redeemability_judgement(judgement) -> JudgeStatus | None:
    if not isinstance(judgement, RedeemabilityJudgement):
        judgement = RedeemabilityJudgement.model_validate(judgement)
    if judgement.confidence != "high":
        return None
    contract = judgement.contract_redeemable
    im = judgement.im_redeemable
    if contract in ("conditional", "unknown") or im in ("conditional", "unknown"):
        return None
    if contract == im:
        return JudgeStatus.SAME
    return JudgeStatus.DIFFERENT


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
