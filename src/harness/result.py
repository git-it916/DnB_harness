"""HarnessResult — 하네스 1회 실행 출력 (docs/INTERFACES.md §4).

abox 는 rdflib.Graph 대신 Turtle 문자열로 보관 (직렬화·저장 단순화).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.guards.base import GuardEvent
from src.pipelines.cross_check import CrossCheckResult
from src.schemas.extraction import ExtractionResult

HarnessMode = Literal["baseline", "ontology", "guard"]


class HarnessResult(BaseModel):
    """하네스 1회 실행 결과.

    모드별 채워지는 필드:
        baseline : extraction 만 (가드/ABox/SHACL/cross_check 없음)
        ontology : + abox_ttl, shacl_*, cross_check (진단; 가드 미집행)
        guard    : + guard_log (G1/G2/G3 집행)
    """

    model_config = ConfigDict(extra="forbid")

    mode: HarnessMode
    extraction: ExtractionResult
    guard_log: list[GuardEvent] = Field(default_factory=list)
    # guard 모드에서 G1 치명 실패로 ABox/SHACL/cross_check 를 못 돌렸는지 표시.
    # (baseline 의 cross_check=None 과 구분하기 위함 — INTERFACES §3 '가드⊃온톨로지')
    g1_fatal: bool = False
    abox_ttl: str | None = None
    shacl_conforms: bool | None = None
    shacl_report_text: str | None = None
    cross_check: list[CrossCheckResult] | None = None

    # 운영 메타
    total_latency_ms: int = 0
    llm_call_count: int = 0
    llm_total_tokens: int = 0
    llm_total_cost_usd: float = 0.0
