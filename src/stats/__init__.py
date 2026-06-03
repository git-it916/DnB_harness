"""통계 — 3조건 비교의 유의성 검정.

- McNemar : (baseline vs guard) 짝지은 합격/불합격 차이의 유의성.
- Bootstrap : mode 별 F1 의 95% 신뢰구간.

docs/INTERFACES.md §8.
"""

from src.stats.bootstrap import BootstrapCI, bootstrap_f1_ci
from src.stats.mcnemar import McNemarResult, mcnemar_test
from src.stats.paired import aligned_correctness, mismatch_arrays, write_stats_csv

__all__ = [
    "McNemarResult",
    "mcnemar_test",
    "BootstrapCI",
    "bootstrap_f1_ci",
    "aligned_correctness",
    "mismatch_arrays",
    "write_stats_csv",
]
