"""채점 엔진 — 케이스별 하네스 예측 → score.json (docs/INTERFACES.md §6).

채점 정의 (GOLDENSET.md §7):
    TP = (gold=mismatch) ∩ (pred=mismatch)
    FP = (gold=match)    ∩ (pred=mismatch)
    FN = (gold=mismatch) ∩ (pred=match | missing)
    TN = (gold=match)    ∩ (pred=match | missing)
    gold=missing 은 confusion 분모·분자 모두 제외 (재현율에 페널티 안 줌).

    환각률(hallucination_rate) = (gold=missing 인데 pred≠missing) / (gold=missing 총수)
        → 정당하게 부재한 필드를 하네스가 값으로 채웠는가.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.scoring.breakdown import (
    Scored,
    by_difficulty,
    by_field,
    by_mutation,
    by_signal,
    confusion_of,
)
from src.scoring.labels import GoldLabel, predicted_label

SCHEMA_VERSION = "v0"


class CaseRecord(BaseModel):
    """한 골든 케이스에 대한 하네스 예측 (채점기 입력 단위)."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    field: str
    gold_label: GoldLabel
    difficulty: str
    mutation_type: str
    harness_signal: str
    final_status: str
    final_reason_code: str | None = None
    guard_rejections: list[str] = Field(default_factory=list)
    latency_ms: int = 0


def _classify(record: CaseRecord) -> Scored:
    guard_caught = bool(record.guard_rejections)
    pred = predicted_label(record.final_status, guard_caught=guard_caught)
    gold = record.gold_label

    gold_mm = gold == GoldLabel.MISMATCH
    pred_mm = pred == GoldLabel.MISMATCH

    # 이진 분류(mismatch=positive) 기준. GOLDENSET §7 은 FN/TN 를 pred=match 로만
    # 적었으나, pred=missing(가드 미적용 시 측 결측)도 'mismatch 아님'으로 본다
    # → gold=mismatch&pred=missing 은 FN, gold=match&pred=missing 은 TN.
    # (이 확장 해석은 PM 비준 대상 — docs/GOLDENSET.md §7 문구 갱신 필요.)
    if gold == GoldLabel.MISSING:
        bucket = "MISSING"
        correct = pred == GoldLabel.MISSING  # 환각하지 않으면 정답
    elif gold_mm and pred_mm:
        bucket, correct = "TP", True
    elif gold_mm and not pred_mm:
        bucket, correct = "FN", False
    elif (not gold_mm) and pred_mm:
        bucket, correct = "FP", False
    else:
        bucket, correct = "TN", True

    return Scored(
        case_id=record.case_id,
        field=record.field,
        difficulty=record.difficulty,
        mutation_type=record.mutation_type,
        harness_signal=record.harness_signal,
        gold=gold,
        pred=pred,
        bucket=bucket,
        correct=correct,
    )


def _round(value: float, digits: int = 4) -> float:
    return round(value, digits)


def score_cases(
    records: list[CaseRecord],
    *,
    mode: str = "guard",
    golden_version: str = "v0.1",
    run_id: str = "adhoc",
) -> dict:
    """케이스별 예측 레코드를 score.json dict 로 채점한다."""
    scored = [_classify(r) for r in records]
    conf = confusion_of(scored)

    missing_total = sum(1 for s in scored if s.gold == GoldLabel.MISSING)
    hallucinated = sum(
        1 for s in scored if s.gold == GoldLabel.MISSING and s.pred != GoldLabel.MISSING
    )
    hallucination_rate = hallucinated / missing_total if missing_total else 0.0

    cases = [
        {
            "case_id": s.case_id,
            "field": s.field,
            "gold_label": s.gold.value,
            "predicted_label": s.pred.value,
            "correct": s.correct,
            "final_status": r.final_status,
            "reason_code": r.final_reason_code,
            "guard_rejections": r.guard_rejections,
            "latency_ms": r.latency_ms,
        }
        for s, r in zip(scored, records)
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": mode,
        "golden_version": golden_version,
        "n_cases": len(records),
        "metrics": {
            "accuracy": _round(conf.accuracy),
            "precision": _round(conf.precision),
            "recall": _round(conf.recall),
            "f1": _round(conf.f1),
            "hallucination_rate": _round(hallucination_rate),
        },
        "confusion": {
            "tp": conf.tp,
            "fp": conf.fp,
            "fn": conf.fn,
            "tn": conf.tn,
            "missing_excluded": conf.missing,
        },
        "by_field": by_field(scored),
        "by_difficulty": by_difficulty(scored),
        "by_mutation": by_mutation(scored),
        "by_signal": by_signal(scored),
        "cases": cases,
    }
