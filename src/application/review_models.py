"""Stable application models exposed to the local review UI.

The research-layer CrossCheckResult is intentionally preserved.  These models
wrap it with operational concepts such as human review and alias resolution.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.guards.base import GuardEvent
from src.pipelines.cross_check import CrossCheckValue
from src.schemas.extraction import ExtractionResult

EffectiveStatus = Literal[
    "match",
    "mismatch",
    "needs_human_review",
    "missing_evidence",
]
ResolutionSource = Literal[
    "deterministic",
    "alias_registry",
    "llm_judge",
    "human",
    "unresolved",
]


class StrictApplicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JudgeSuggestion(StrictApplicationModel):
    status: Literal["same", "different"]
    reason: str
    reason_code: str = "generic_semantic_judge"


class HumanDecisionView(StrictApplicationModel):
    decision: Literal["same", "different", "unknown"]
    note: str = ""
    remember_alias: bool = False
    decided_at: str


class ReviewFieldResult(StrictApplicationModel):
    field: str
    label: str
    system_status: str
    effective_status: EffectiveStatus
    resolution_source: ResolutionSource
    requires_human_review: bool
    reason_code: str
    reason: str
    contract: CrossCheckValue
    im: CrossCheckValue
    canonical: dict[str, Any] | None = None
    judge_suggestion: JudgeSuggestion | None = None
    guard_events: list[GuardEvent] = Field(default_factory=list)
    human_decision: HumanDecisionView | None = None


class ReviewSummary(StrictApplicationModel):
    total: int
    match: int
    mismatch: int
    needs_human_review: int
    missing_evidence: int


class ReviewResult(StrictApplicationModel):
    schema_version: Literal["review-v1"] = "review-v1"
    run_id: str
    strategy: Literal["ontology_policy", "ontology_policy_judge"]
    extraction: ExtractionResult
    fields: list[ReviewFieldResult]
    summary: ReviewSummary
    guard_log: list[GuardEvent] = Field(default_factory=list)
    shacl_conforms: bool
    shacl_report_text: str
    abox_ttl: str
    model: str
    model_digest: str
    total_latency_ms: int
    llm_total_tokens: int


def summarize_fields(fields: list[ReviewFieldResult]) -> ReviewSummary:
    counts = {
        "match": 0,
        "mismatch": 0,
        "needs_human_review": 0,
        "missing_evidence": 0,
    }
    for field in fields:
        counts[field.effective_status] += 1
    return ReviewSummary(total=len(fields), **counts)
