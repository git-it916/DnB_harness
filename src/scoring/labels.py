"""gold_label ↔ FinalCheckStatus 매핑 (docs/GOLDENSET.md §7 단일 진실 소스)."""

from __future__ import annotations

from enum import StrEnum

from src.pipelines.cross_check import FinalCheckStatus


class GoldLabel(StrEnum):
    """골든셋 정답 라벨 (GOLDENSET.md §4.2)."""

    MATCH = "match"
    MISMATCH = "mismatch"
    MISSING = "missing"


class PredictedLabel(StrEnum):
    """하네스 예측 라벨. review 는 자동 확정이 아닌 사람 검토 큐다."""

    MATCH = "match"
    MISMATCH = "mismatch"
    REVIEW = "review"
    MISSING = "missing"


# GOLDENSET.md §7 — 하네스 final_status 를 표시용 예측 라벨로 매핑한다.
FINAL_TO_PREDICTED: dict[FinalCheckStatus, PredictedLabel] = {
    FinalCheckStatus.EXACT_MATCH: PredictedLabel.MATCH,
    FinalCheckStatus.SAME_AFTER_NORMALIZATION: PredictedLabel.MATCH,
    FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION: PredictedLabel.MISMATCH,
    FinalCheckStatus.NEEDS_REVIEW: PredictedLabel.REVIEW,
    FinalCheckStatus.MISSING_EVIDENCE: PredictedLabel.MISSING,
}

# FinalCheckStatus 에 새 멤버가 추가되면 즉시 잡아낸다 (조용한 KeyError 방지).
assert set(FINAL_TO_PREDICTED) == set(FinalCheckStatus), (
    "FINAL_TO_PREDICTED 매핑 누락: "
    f"{set(FinalCheckStatus) - set(FINAL_TO_PREDICTED)}"
)


def predicted_label(
    final_status: FinalCheckStatus | str, guard_caught: bool = False
) -> PredictedLabel:
    """하네스 출력(final_status + 가드 결과) → 예측 라벨.

    Args:
        final_status: cross_check 의 FinalCheckStatus (enum 또는 문자열).
        guard_caught: 해당 필드에 가드 reject 가 있었는가.
            True 이면 가드가 문제를 '잡은' 것이므로, 측이 null화되어
            final_status 가 missing_evidence 로 나와도 mismatch 로 본다
            가드 reject 는 자동으로 잡은 불일치로 본다.

    Returns:
        PredictedLabel (match | mismatch | review | missing).
    """
    if guard_caught:
        return PredictedLabel.MISMATCH
    status = FinalCheckStatus(final_status)
    return FINAL_TO_PREDICTED[status]
