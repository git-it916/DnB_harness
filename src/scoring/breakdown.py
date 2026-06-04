"""채점 세부 분해 (by_field / by_difficulty / by_mutation / by_signal).

score.json 의 분해 블록을 만든다 (docs/INTERFACES.md §6).
입력은 scorer 가 만든 Scored 리스트 (record + pred + bucket + correct).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Sequence

from src.scoring.labels import GoldLabel, PredictedLabel


@dataclass(frozen=True)
class Scored:
    """한 케이스의 채점 결과 (분해/집계의 원자 단위)."""

    case_id: str
    field: str
    difficulty: str
    mutation_type: str
    harness_signal: str
    gold: GoldLabel
    pred: PredictedLabel
    bucket: str  # "TP" | "FP" | "FN" | "TN" | "REVIEW" | "MISSING"
    correct: bool


@dataclass(frozen=True)
class Confusion:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    review: int = 0
    missing: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        denom = self.tp + self.tn + self.fp + self.fn + self.review
        return (self.tp + self.tn) / denom if denom else 0.0


def confusion_of(scored: Sequence[Scored]) -> Confusion:
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "REVIEW": 0, "MISSING": 0}
    for item in scored:
        counts[item.bucket] += 1
    return Confusion(
        tp=counts["TP"],
        fp=counts["FP"],
        fn=counts["FN"],
        tn=counts["TN"],
        review=counts["REVIEW"],
        missing=counts["MISSING"],
    )


def _group(scored: Sequence[Scored], key_fn: Callable[[Scored], str]) -> dict[str, list[Scored]]:
    buckets: dict[str, list[Scored]] = defaultdict(list)
    for item in scored:
        buckets[key_fn(item)].append(item)
    return dict(buckets)


def _round(value: float, digits: int = 4) -> float:
    return round(value, digits)


def by_field(scored: Sequence[Scored]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for field, items in _group(scored, lambda s: s.field).items():
        conf = confusion_of(items)
        out[field] = {
            "n": len(items),
            "correct": sum(1 for s in items if s.correct),
            "recall": _round(conf.recall),
            "f1": _round(conf.f1),
        }
    return out


def by_difficulty(scored: Sequence[Scored]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for difficulty, items in _group(scored, lambda s: s.difficulty).items():
        conf = confusion_of(items)
        out[difficulty] = {
            "n": len(items),
            "accuracy": _round(conf.accuracy),
            "recall": _round(conf.recall),
        }
    return out


def by_mutation(scored: Sequence[Scored]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for mutation, items in _group(scored, lambda s: s.mutation_type).items():
        conf = confusion_of(items)
        out[mutation] = {
            "n": len(items),
            "caught": conf.tp,
            "recall": _round(conf.recall),
        }
    return out


def by_signal(scored: Sequence[Scored]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for signal, items in _group(scored, lambda s: s.harness_signal).items():
        conf = confusion_of(items)
        expected = conf.tp + conf.fn  # positive(=mismatch) 골든 케이스 수
        out[signal] = {
            "expected": expected,
            "caught": conf.tp,
            "hit_rate": _round(conf.tp / expected) if expected else 0.0,
        }
    return out
