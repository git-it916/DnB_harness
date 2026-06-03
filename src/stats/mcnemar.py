"""McNemar 검정 — 짝지은 이진 결과(정/오답) 두 조건의 차이 유의성.

소표본(n_discordant < 25)은 정확 이항검정, 그 외엔 연속성 보정 카이제곱.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from scipy.stats import binomtest, chi2


@dataclass(frozen=True)
class McNemarResult:
    """McNemar 검정 결과.

    statistic 은 method 에 따라 의미가 다르다:
        - "exact_binomial"   : min(b, c) (이항검정의 관측값, 정수)
        - "chi2_continuity"  : Yates 연속성 보정 카이제곱 통계량
        - "no_discordant"    : 0.0 (불일치 케이스 없음)
    해석 시 반드시 method 를 함께 확인할 것.
    """

    b: int  # a 정답 & b 오답
    c: int  # a 오답 & b 정답
    n_discordant: int
    statistic: float
    p_value: float
    method: str


def mcnemar_test(
    correct_a: Sequence[bool],
    correct_b: Sequence[bool],
    *,
    exact: bool | None = None,
) -> McNemarResult:
    """두 조건의 케이스별 정/오답 배열로 McNemar 검정.

    Args:
        correct_a / correct_b: 같은 케이스 순서로 정렬된 정답 여부.
        exact: True 면 정확 이항검정, False 면 카이제곱. None 이면 자동
            (discordant < 25 → 정확).

    Raises:
        ValueError: 두 배열 길이가 다를 때.
    """
    if len(correct_a) != len(correct_b):
        raise ValueError("correct_a 와 correct_b 의 길이가 다릅니다")

    b = sum(1 for x, y in zip(correct_a, correct_b) if x and not y)
    c = sum(1 for x, y in zip(correct_a, correct_b) if (not x) and y)
    n = b + c

    if n == 0:
        return McNemarResult(b, c, 0, 0.0, 1.0, "no_discordant")

    use_exact = (n < 25) if exact is None else exact
    if use_exact:
        result = binomtest(min(b, c), n, 0.5, alternative="two-sided")
        return McNemarResult(b, c, n, float(min(b, c)), float(result.pvalue), "exact_binomial")

    statistic = (abs(b - c) - 1) ** 2 / n  # 연속성 보정
    p_value = float(chi2.sf(statistic, df=1))
    return McNemarResult(b, c, n, float(statistic), p_value, "chi2_continuity")
