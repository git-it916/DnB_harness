"""score.json → 통계 입력 (짝지은 정/오답, mismatch 배열, McNemar CSV).

docs/INTERFACES.md §8 의 통계 입력 표를 만든다.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Mapping

logger = logging.getLogger(__name__)


def _cases_by_id(report: Mapping) -> dict[str, dict]:
    return {c["case_id"]: c for c in report.get("cases", [])}


def aligned_correctness(
    report_a: Mapping, report_b: Mapping
) -> tuple[list[bool], list[bool]]:
    """두 리포트의 공통 case_id 에 대해 정/오답 배열을 같은 순서로 반환."""
    a = _cases_by_id(report_a)
    b = _cases_by_id(report_b)
    common = [cid for cid in a if cid in b]
    return [bool(a[cid]["correct"]) for cid in common], [bool(b[cid]["correct"]) for cid in common]


def mismatch_arrays(report: Mapping) -> tuple[list[bool], list[bool]]:
    """리포트에서 (gold_mismatch, pred_mismatch) 배열. gold=missing 케이스는 제외."""
    gold: list[bool] = []
    pred: list[bool] = []
    for case in report.get("cases", []):
        if case["gold_label"] == "missing":
            continue
        gold.append(case["gold_label"] == "mismatch")
        pred.append(case["predicted_label"] == "mismatch")
    return gold, pred


def write_stats_csv(reports_by_mode: Mapping[str, Mapping], path: Path | str) -> Path:
    """모드별 예측 라벨을 case_id 로 짝지어 McNemar 입력 CSV 로 저장.

    컬럼: case_id, gold_label, mode_<each mode> (예측 라벨).
    """
    modes = list(reports_by_mode.keys())
    # 모든 모드에 공통으로 존재하는 case_id (정렬 안정성 위해 첫 모드 순서 유지)
    first = reports_by_mode[modes[0]]
    case_ids = [c["case_id"] for c in first.get("cases", [])]
    by_mode_cases = {m: _cases_by_id(r) for m, r in reports_by_mode.items()}

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    skipped: list[str] = []
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "gold_label"] + [f"mode_{m}" for m in modes])
        for cid in case_ids:
            if not all(cid in by_mode_cases[m] for m in modes):
                skipped.append(cid)
                continue
            gold = by_mode_cases[modes[0]][cid]["gold_label"]
            row = [cid, gold] + [by_mode_cases[m][cid]["predicted_label"] for m in modes]
            writer.writerow(row)
    if skipped:
        logger.warning(
            "write_stats_csv: %d개 case_id 가 일부 모드에 없어 제외됨: %s",
            len(skipped),
            skipped,
        )
    return out
