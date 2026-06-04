import json
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

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


class MaturityJudgement(StrictJudgeModel):
    field: Literal["fund.maturity_date"]
    contract_maturity_date: str | None
    im_maturity_date: str | None
    contract_basis: Literal["absolute_date", "derived_from_inception_duration", "conditional", "unknown"]
    im_basis: Literal["absolute_date", "derived_from_inception_duration", "conditional", "unknown"]
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


class RedemptionFeeJudgement(StrictJudgeModel):
    field: Literal["redemption_terms.redemption_fee"]
    contract_fee_status: Literal[
        "fee_specified",
        "no_fee",
        "not_applicable_no_redemption",
        "conditional_or_exception",
        "unknown",
    ]
    im_fee_status: Literal[
        "fee_specified",
        "no_fee",
        "not_applicable_no_redemption",
        "conditional_or_exception",
        "unknown",
    ]
    contract_fee_value: str | None = None
    im_fee_value: str | None = None
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


_MATURITY_SYSTEM_PROMPT = """\
You classify maturity dates for Korean private fund documents.

Use only the extracted field text and the provided inception date extraction. Return JSON only:
- field: must be "fund.maturity_date"
- contract_maturity_date: ISO YYYY-MM-DD or null
- im_maturity_date: ISO YYYY-MM-DD or null
- contract_basis: "absolute_date" | "derived_from_inception_duration" | "conditional" | "unknown"
- im_basis: "absolute_date" | "derived_from_inception_duration" | "conditional" | "unknown"
- confidence: "high" | "medium" | "low"
- reason_code: short snake_case code
- contract_evidence: short phrase from contract text
- im_evidence: short phrase from IM text
- reason: one short Korean explanation

If a side gives a duration such as 2 years, derive the date only when same-side inception date is provided.
If early liquidation, extension, or investor consent is mentioned but the normal maturity is still explicit, classify the normal maturity date and mention the condition in reason.
Use high confidence only when both normalized maturity dates are explicit or derivable from the provided extraction values.
Do not decide same/different directly.

Examples:
- inception 2025-07-22 + "펀드만기 2년" => maturity_date 2027-07-22, basis "derived_from_inception_duration".
- inception 2025-07-22 + "펀드만기 3년" => maturity_date 2028-07-22, basis "derived_from_inception_duration".
- "최초설정일로부터 2027년 7월 22일까지" => maturity_date 2027-07-22, basis "absolute_date".
- Parenthetical early liquidation or investor-consent wording does not change the normal maturity date.
"""


def judge_maturity(
    result: CrossCheckResult,
    *,
    contract_inception_raw: str | None,
    im_inception_raw: str | None,
    llm: JudgeLLM | None = None,
) -> MaturityJudgement:
    if result.field != "fund.maturity_date":
        raise ValueError(f"maturity judge cannot handle field: {result.field}")
    judge_llm = llm or AnthropicJSONClient()
    payload = judge_llm.complete_json(
        system_prompt=_MATURITY_SYSTEM_PROMPT,
        user_prompt=json.dumps(
            {
                "field": result.field,
                "label": result.label,
                "contract_raw_text": result.contract.raw_text,
                "im_raw_text": result.im.raw_text,
                "contract_inception_raw_text": contract_inception_raw,
                "im_inception_raw_text": im_inception_raw,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    return MaturityJudgement.model_validate(payload)


def resolve_maturity_judgement(judgement) -> JudgeStatus | None:
    if not isinstance(judgement, MaturityJudgement):
        judgement = MaturityJudgement.model_validate(judgement)
    if judgement.confidence != "high":
        return None
    if judgement.contract_basis in ("conditional", "unknown") or judgement.im_basis in ("conditional", "unknown"):
        return None
    if not judgement.contract_maturity_date or not judgement.im_maturity_date:
        return None
    if judgement.contract_maturity_date == judgement.im_maturity_date:
        return JudgeStatus.SAME
    return JudgeStatus.DIFFERENT


_REDEMPTION_FEE_SYSTEM_PROMPT = """\
You classify redemption fee applicability for Korean private fund documents.

Use the same enum for contract and IM. Return JSON only:
- field: must be "redemption_terms.redemption_fee"
- contract_fee_status: "fee_specified" | "no_fee" | "not_applicable_no_redemption" | "conditional_or_exception" | "unknown"
- im_fee_status: "fee_specified" | "no_fee" | "not_applicable_no_redemption" | "conditional_or_exception" | "unknown"
- contract_fee_value: fee text if explicitly specified, otherwise null
- im_fee_value: fee text if explicitly specified, otherwise null
- confidence: "high" | "medium" | "low"
- reason_code: short snake_case code
- contract_evidence: short phrase from contract text
- im_evidence: short phrase from IM text
- reason: one short Korean explanation

Definitions for the redemption_fee field:
- "fee_specified": a redemption fee rate/amount/formula is explicitly stated.
- "no_fee": the redemption fee is stated as none, waived, or not applicable.
- "not_applicable_no_redemption": redemption is impossible/closed-ended, so a redemption fee does not apply.
- "conditional_or_exception": fee depends on conditions or exceptions.
- "unknown": evidence is insufficient.

Do not decide same/different directly. Classify each side independently.
"""


def judge_redemption_fee(
    result: CrossCheckResult,
    *,
    llm: JudgeLLM | None = None,
) -> RedemptionFeeJudgement:
    if result.field != "redemption_terms.redemption_fee":
        raise ValueError(f"redemption fee judge cannot handle field: {result.field}")
    judge_llm = llm or AnthropicJSONClient()
    payload = judge_llm.complete_json(
        system_prompt=_REDEMPTION_FEE_SYSTEM_PROMPT,
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
    return RedemptionFeeJudgement.model_validate(payload)


def resolve_redemption_fee_judgement(judgement) -> JudgeStatus | None:
    if not isinstance(judgement, RedemptionFeeJudgement):
        judgement = RedemptionFeeJudgement.model_validate(judgement)
    if judgement.confidence != "high":
        return None
    contract = judgement.contract_fee_status
    im = judgement.im_fee_status
    review_statuses = {"conditional_or_exception", "unknown"}
    if contract in review_statuses or im in review_statuses:
        return None
    no_fee_equivalent = {"no_fee", "not_applicable_no_redemption"}
    if contract in no_fee_equivalent and im in no_fee_equivalent:
        return JudgeStatus.SAME
    if contract == "fee_specified" and im == "fee_specified":
        if judgement.contract_fee_value and judgement.im_fee_value:
            return (
                JudgeStatus.SAME
                if judgement.contract_fee_value == judgement.im_fee_value
                else JudgeStatus.DIFFERENT
            )
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
