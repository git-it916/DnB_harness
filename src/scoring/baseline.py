"""Baseline 판정 — LLM 단독(온톨로지·가드·정규화 없음)으로 각 골든 케이스를 판정.

3조건의 ① baseline 조건. guard/ontology 와 '같은 골든 raw_text' 를 입력으로 받되,
하네스 로직 대신 LLM 이 직접 match/mismatch/missing 을 고른다. 같은 입력·다른 방법
이라 온톨로지+하네스의 순효과를 분리해 보여준다.
"""

from __future__ import annotations

import json
from enum import StrEnum

from src.client.ollama_client import OllamaClient
from src.pipelines.cross_check import FinalCheckStatus
from src.scoring.golden import GoldenCase
from src.scoring.scorer import CaseRecord


class BaselineVerdict(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    MISSING = "missing"


# LLM 판정 → 채점기가 이해하는 FinalCheckStatus 로 변환.
_VERDICT_TO_FINAL: dict[BaselineVerdict, FinalCheckStatus] = {
    BaselineVerdict.MATCH: FinalCheckStatus.EXACT_MATCH,
    BaselineVerdict.MISMATCH: FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION,
    BaselineVerdict.MISSING: FinalCheckStatus.MISSING_EVIDENCE,
}

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["match", "mismatch", "missing"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
}

_PROMPT = """당신은 신탁계약서와 투자제안서(IM)를 비교하는 검토자입니다.
아래 한 항목에 대해 두 문서의 값이 '같은 사실'인지 직접 판정하세요.

항목: {label}
신탁계약서 값: {contract}
IM 값: {im}

판정 기준:
- match   : 표기·단위·순서가 달라도 같은 사실
- mismatch : 사실이 실제로 다름
- missing : 한쪽 이상에 정보가 없음

JSON 으로만 답하세요: {{"verdict": "match|mismatch|missing", "reason": "한 줄 근거"}}"""


def verdict_to_final_status(verdict: BaselineVerdict | str) -> FinalCheckStatus:
    """baseline 판정 → FinalCheckStatus (채점기 입력용)."""
    return _VERDICT_TO_FINAL[BaselineVerdict(verdict)]


def _parse_verdict(text: str) -> BaselineVerdict:
    """LLM 응답에서 verdict 추출. JSON 우선, 실패 시 키워드 폴백."""
    try:
        data = json.loads(text)
        return BaselineVerdict(data["verdict"])
    except (json.JSONDecodeError, KeyError, ValueError):
        lowered = text.lower()
        for verdict in (BaselineVerdict.MISMATCH, BaselineVerdict.MISSING, BaselineVerdict.MATCH):
            if verdict.value in lowered:
                return verdict
        # 끝내 못 읽으면 보수적으로 missing (환각 방지 쪽)
        return BaselineVerdict.MISSING


def judge_case(client: OllamaClient, case: GoldenCase) -> BaselineVerdict:
    """LLM 단독으로 한 케이스 판정."""
    prompt = _PROMPT.format(
        label=case.label,
        contract=case.contract_raw or "(없음)",
        im=case.im_raw or "(없음)",
    )
    result = client.generate(prompt=prompt, json_schema=_VERDICT_SCHEMA)
    return _parse_verdict(result.response_text)


def evaluate_baseline(client: OllamaClient, cases: list[GoldenCase]) -> list[CaseRecord]:
    """골든 케이스들을 LLM 단독 판정으로 채점 레코드화 (가드/온톨로지 없음)."""
    records: list[CaseRecord] = []
    for case in cases:
        verdict = judge_case(client, case)
        records.append(
            CaseRecord(
                case_id=case.case_id,
                field=case.field,
                gold_label=case.gold_label,
                difficulty=case.difficulty,
                mutation_type=case.mutation_type,
                harness_signal=case.harness_signal,
                final_status=str(verdict_to_final_status(verdict)),
                final_reason_code="baseline_llm_verdict",
                guard_rejections=[],
            )
        )
    return records
