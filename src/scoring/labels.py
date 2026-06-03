"""gold_label ↔ FinalCheckStatus 매핑 (docs/GOLDENSET.md §7 단일 진실 소스)."""

from __future__ import annotations

from enum import StrEnum

from src.pipelines.cross_check import FinalCheckStatus


class GoldLabel(StrEnum):
    """골든셋 정답 라벨 (GOLDENSET.md §4.2)."""

    MATCH = "match"
    MISMATCH = "mismatch"
    MISSING = "missing"


# GOLDENSET.md §7 — 이 매핑이 바뀌면 모든 점수가 바뀐다.
GOLD_TO_FINAL: dict[GoldLabel, frozenset[FinalCheckStatus]] = {
    GoldLabel.MATCH: frozenset(
        {FinalCheckStatus.EXACT_MATCH, FinalCheckStatus.SAME_AFTER_NORMALIZATION}
    ),
    GoldLabel.MISMATCH: frozenset(
        {FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION, FinalCheckStatus.NEEDS_REVIEW}
    ),
    GoldLabel.MISSING: frozenset({FinalCheckStatus.MISSING_EVIDENCE}),
}

# 역매핑 (final_status -> gold-style 라벨). GOLD_TO_FINAL 에서 자동 생성.
_FINAL_TO_GOLD: dict[FinalCheckStatus, GoldLabel] = {
    final_status: gold_label
    for gold_label, final_statuses in GOLD_TO_FINAL.items()
    for final_status in final_statuses
}

# FinalCheckStatus 에 새 멤버가 추가되면 즉시 잡아낸다 (조용한 KeyError 방지).
assert set(_FINAL_TO_GOLD) == set(FinalCheckStatus), (
    "GOLD_TO_FINAL 매핑 누락: "
    f"{set(FinalCheckStatus) - set(_FINAL_TO_GOLD)}"
)


def predicted_label(
    final_status: FinalCheckStatus | str, guard_caught: bool = False
) -> GoldLabel:
    """하네스 출력(final_status + 가드 결과) → 예측 gold-style 라벨.

    Args:
        final_status: cross_check 의 FinalCheckStatus (enum 또는 문자열).
        guard_caught: 해당 필드에 가드 reject 가 있었는가.
            True 이면 가드가 문제를 '잡은' 것이므로, 측이 null화되어
            final_status 가 missing_evidence 로 나와도 mismatch 로 본다
            (재현율 우선 — GOLDENSET.md §7).

    Returns:
        GoldLabel (match | mismatch | missing).
    """
    if guard_caught:
        return GoldLabel.MISMATCH
    status = FinalCheckStatus(final_status)
    return _FINAL_TO_GOLD[status]
