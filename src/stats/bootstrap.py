"""부트스트랩 신뢰구간 — F1 의 95% CI (percentile 방법).

mismatch=positive 이진 분류 기준 F1. 케이스 인덱스를 복원추출.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class BootstrapCI:
    point: float
    lo: float
    hi: float
    n_boot: int
    ci: float


def _f1(gold: np.ndarray, pred: np.ndarray) -> float:
    tp = int(np.sum(gold & pred))
    fp = int(np.sum(~gold & pred))
    fn = int(np.sum(gold & ~pred))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0


def bootstrap_f1_ci(
    gold: Sequence[bool],
    pred: Sequence[bool],
    *,
    n_boot: int = 2000,
    ci: float = 0.95,
    seed: int = 42,
) -> BootstrapCI:
    """F1 의 부트스트랩 percentile 신뢰구간.

    Args:
        gold / pred: mismatch 여부(=positive) 불리언 배열 (missing 제외 후).
        n_boot: 부트스트랩 반복 수.
        ci: 신뢰수준 (0.95 = 95%).
        seed: 재현성 시드.

    Raises:
        ValueError: 입력 길이가 0 이거나 두 배열 길이가 다를 때.
    """
    if len(gold) != len(pred):
        raise ValueError("gold 와 pred 의 길이가 다릅니다")
    n = len(gold)
    if n == 0:
        raise ValueError("빈 입력으로는 부트스트랩 불가")

    g = np.asarray(gold, dtype=bool)
    p = np.asarray(pred, dtype=bool)
    rng = np.random.default_rng(seed)

    stats = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        stats[i] = _f1(g[idx], p[idx])

    alpha = (1.0 - ci) / 2.0
    lo = float(np.quantile(stats, alpha))
    hi = float(np.quantile(stats, 1.0 - alpha))
    return BootstrapCI(point=_f1(g, p), lo=lo, hi=hi, n_boot=n_boot, ci=ci)
