"""Stage D 통계 테스트 (McNemar + 부트스트랩). docs/INTERFACES.md §8."""

from __future__ import annotations

from src.stats.bootstrap import bootstrap_f1_ci
from src.stats.mcnemar import mcnemar_test
from src.stats.paired import aligned_correctness, mismatch_arrays


# ── McNemar ──────────────────────────────────────────────────────────────────

def test_mcnemar_no_difference_high_pvalue():
    # 동일한 정오답 -> 불일치(discordant) 0 -> p=1.0
    a = [True, True, False, False]
    res = mcnemar_test(a, a)
    assert res.b == 0 and res.c == 0
    assert res.p_value == 1.0


def test_mcnemar_guard_improves_counts_discordant():
    # baseline 다 틀림, guard 다 맞음 -> c=4, b=0
    baseline = [False, False, False, False]
    guard = [True, True, True, True]
    res = mcnemar_test(baseline, guard)
    assert res.b == 0 and res.c == 4
    assert res.p_value < 0.15  # 4-0 exact binomial two-sided = 0.125


def test_mcnemar_length_mismatch_raises():
    import pytest

    with pytest.raises(ValueError):
        mcnemar_test([True], [True, False])


# ── Bootstrap ────────────────────────────────────────────────────────────────

def test_bootstrap_f1_ci_brackets_point_and_is_deterministic():
    gold = [True, True, True, False, False, False]
    pred = [True, True, False, False, False, True]  # tp=2 fn=1 fp=1 -> F1=0.667
    ci1 = bootstrap_f1_ci(gold, pred, n_boot=500, seed=42)
    ci2 = bootstrap_f1_ci(gold, pred, n_boot=500, seed=42)
    assert ci1.lo <= ci1.point <= ci1.hi
    assert 0.0 <= ci1.lo <= ci1.hi <= 1.0
    assert (ci1.lo, ci1.point, ci1.hi) == (ci2.lo, ci2.point, ci2.hi)  # seed 재현성


def test_bootstrap_perfect_predictions_ci_is_one():
    gold = [True, True, False, False]
    pred = [True, True, False, False]
    ci = bootstrap_f1_ci(gold, pred, n_boot=200, seed=1)
    assert ci.point == 1.0 and ci.hi == 1.0


# ── paired (score.json -> 통계 입력) ─────────────────────────────────────────

def _report(cases: list[dict]) -> dict:
    return {"mode": "x", "cases": cases}


def test_aligned_correctness_matches_by_case_id():
    a = _report([
        {"case_id": "C1", "correct": True, "gold_label": "mismatch", "predicted_label": "mismatch"},
        {"case_id": "C2", "correct": False, "gold_label": "match", "predicted_label": "mismatch"},
    ])
    b = _report([
        {"case_id": "C1", "correct": False, "gold_label": "mismatch", "predicted_label": "match"},
        {"case_id": "C2", "correct": True, "gold_label": "match", "predicted_label": "match"},
    ])
    ca, cb = aligned_correctness(a, b)
    assert ca == [True, False] and cb == [False, True]


def test_mismatch_arrays_excludes_missing():
    rep = _report([
        {"case_id": "C1", "gold_label": "mismatch", "predicted_label": "mismatch"},
        {"case_id": "C2", "gold_label": "missing", "predicted_label": "missing"},
        {"case_id": "C3", "gold_label": "match", "predicted_label": "mismatch"},
    ])
    gold, pred = mismatch_arrays(rep)
    assert gold == [True, False]  # C2(missing) 제외
    assert pred == [True, True]
