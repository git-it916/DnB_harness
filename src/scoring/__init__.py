"""채점 (scoring) — 골든셋 대비 하네스 판정을 점수화한다.

단일 진실 소스:
    - docs/GOLDENSET.md §7  : gold_label ↔ FinalCheckStatus 매핑, TP/FP/FN/TN 정의
    - docs/INTERFACES.md §6 : score.json 출력 스키마
"""

from src.scoring.golden import GoldenCase, load_golden_master
from src.scoring.labels import FINAL_TO_PREDICTED, GoldLabel, PredictedLabel, predicted_label
from src.scoring.scorer import CaseRecord, score_cases

__all__ = [
    "GoldenCase",
    "load_golden_master",
    "FINAL_TO_PREDICTED",
    "GoldLabel",
    "PredictedLabel",
    "predicted_label",
    "CaseRecord",
    "score_cases",
]
