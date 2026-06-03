"""Stage A 채점 모듈 테스트 (TDD).

검증 단일 진실 소스: docs/GOLDENSET.md §7, docs/INTERFACES.md §6.
"""

from __future__ import annotations

import math

from src.pipelines.cross_check import FinalCheckStatus
from src.pipelines.llm_judge import JudgeStatus
from src.scoring.evaluate import evaluate_golden, resolve_with_judge
from src.scoring.golden import GoldenCase, load_golden_master
from src.scoring.labels import GoldLabel, predicted_label
from src.scoring.scorer import CaseRecord, score_cases


# ── labels ────────────────────────────────────────────────────────────────

def test_predicted_label_maps_each_final_status():
    assert predicted_label(FinalCheckStatus.EXACT_MATCH) == GoldLabel.MATCH
    assert predicted_label(FinalCheckStatus.SAME_AFTER_NORMALIZATION) == GoldLabel.MATCH
    assert predicted_label(FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION) == GoldLabel.MISMATCH
    assert predicted_label(FinalCheckStatus.NEEDS_REVIEW) == GoldLabel.MISMATCH
    assert predicted_label(FinalCheckStatus.MISSING_EVIDENCE) == GoldLabel.MISSING


def test_predicted_label_guard_catch_overrides_to_mismatch():
    # 가드가 reject -> 측이 null화되어 missing_evidence 가 나와도 '잡은' 것이므로 mismatch
    assert (
        predicted_label(FinalCheckStatus.MISSING_EVIDENCE, guard_caught=True)
        == GoldLabel.MISMATCH
    )


# ── golden loader ───────────────────────────────────────────────────────────

def test_load_golden_master_reads_30_cases():
    cases = load_golden_master()
    assert len(cases) == 30
    assert all(isinstance(c, GoldenCase) for c in cases)


def test_load_golden_master_parses_types_and_blanks():
    by_id = {c.case_id: c for c in load_golden_master()}

    # 정상 match, 페이지 정수
    c001 = by_id["C001"]
    assert c001.gold_label == GoldLabel.MATCH
    assert c001.contract_page == 2 and c001.im_page == 9

    # 양쪽 누락 -> raw None, page None
    c010 = by_id["C010"]
    assert c010.gold_label == GoldLabel.MISSING
    assert c010.contract_raw is None and c010.contract_page is None
    assert c010.im_raw is None and c010.im_page is None

    # 가짜 인용 page=999 보존
    assert by_id["C029"].im_page == 999


# ── scorer (합성 레코드로 정밀 검증) ─────────────────────────────────────────

def _rec(case_id, gold, final, *, guards=None, difficulty="medium",
         mutation="x", signal="cross_check", field="fund.name") -> CaseRecord:
    return CaseRecord(
        case_id=case_id,
        field=field,
        gold_label=GoldLabel(gold),
        difficulty=difficulty,
        mutation_type=mutation,
        harness_signal=signal,
        final_status=str(final),
        guard_rejections=guards or [],
    )


def _synthetic_records() -> list[CaseRecord]:
    return [
        _rec("R1", "mismatch", FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION),  # TP
        _rec("R2", "mismatch", FinalCheckStatus.NEEDS_REVIEW),                   # TP
        _rec("R3", "mismatch", FinalCheckStatus.EXACT_MATCH),                    # FN
        _rec("R4", "mismatch", FinalCheckStatus.MISSING_EVIDENCE,
             guards=["G2:page_out_of_range"]),                                   # TP (guard)
        _rec("R5", "match", FinalCheckStatus.EXACT_MATCH),                       # TN
        _rec("R6", "match", FinalCheckStatus.NEEDS_REVIEW),                      # FP
        _rec("R7", "missing", FinalCheckStatus.MISSING_EVIDENCE),               # excluded
        _rec("R8", "missing", FinalCheckStatus.EXACT_MATCH),                    # excluded + 환각
    ]


def test_score_cases_confusion_matrix():
    report = score_cases(_synthetic_records(), mode="guard")
    c = report["confusion"]
    assert (c["tp"], c["fp"], c["fn"], c["tn"], c["missing_excluded"]) == (3, 1, 1, 1, 2)


def test_score_cases_metrics():
    m = score_cases(_synthetic_records(), mode="guard")["metrics"]
    assert math.isclose(m["precision"], 0.75, abs_tol=1e-6)
    assert math.isclose(m["recall"], 0.75, abs_tol=1e-6)
    assert math.isclose(m["f1"], 0.75, abs_tol=1e-6)
    assert math.isclose(m["accuracy"], round(4 / 6, 4), abs_tol=1e-9)
    # 환각률: gold=missing 인데 pred!=missing 인 비율 = 1/2
    assert math.isclose(m["hallucination_rate"], 0.5, abs_tol=1e-6)


def test_score_cases_envelope_and_cases():
    report = score_cases(_synthetic_records(), mode="guard",
                         golden_version="v0.1", run_id="exp_test")
    assert report["schema_version"] == "v0"
    assert report["mode"] == "guard"
    assert report["golden_version"] == "v0.1"
    assert report["run_id"] == "exp_test"
    assert report["n_cases"] == 8
    assert len(report["cases"]) == 8
    r4 = next(x for x in report["cases"] if x["case_id"] == "R4")
    assert r4["predicted_label"] == "mismatch"
    assert r4["correct"] is True
    assert "by_difficulty" in report and "by_mutation" in report and "by_signal" in report


# ── 결정적 평가기 (LLM 없이 골든 30케이스를 하네스 로직에 통과) ────────────────

def _records_by_id(mode: str) -> dict[str, CaseRecord]:
    cases = load_golden_master()
    records = evaluate_golden(cases, mode=mode, contract_pages=22, im_pages=32)
    return {r.case_id: r for r in records}


def test_evaluate_ontology_mode_produces_record_per_case():
    records = _records_by_id("ontology")
    assert len(records) == 30


def test_evaluate_missing_cases_are_missing_evidence():
    onto = _records_by_id("ontology")
    for cid in ("C009", "C010", "C016", "C017"):
        assert onto[cid].final_status == FinalCheckStatus.MISSING_EVIDENCE.value
        assert onto[cid].guard_rejections == []


def test_evaluate_fake_citation_caught_only_in_guard_mode():
    # C029: 가짜 인용 page=999 -> G2 가드만 잡는다 (cross_check 만으로는 가드 신호 없음)
    onto = _records_by_id("ontology")["C029"]
    guard = _records_by_id("guard")["C029"]
    assert onto.guard_rejections == []
    assert any("G2" in r for r in guard.guard_rejections)


def test_evaluate_shacl_violation_caught_by_g3_in_guard_mode():
    # C030: IM 운용보수 8.9% (>5%) -> G3 범위 위반 reject
    guard = _records_by_id("guard")["C030"]
    assert any("G3" in r for r in guard.guard_rejections)


def test_evaluate_guard_does_not_false_reject_normal_fee_cases():
    # C011~C013 정상 천분율 (0.89/0.05/0.03%) 은 G3 범위 내 -> reject 없어야
    guard = _records_by_id("guard")
    for cid in ("C011", "C012", "C013"):
        assert guard[cid].guard_rejections == []


def test_evaluate_ontology_policy_mode_uses_canonical_comparison():
    records = evaluate_golden(
        load_golden_master(),
        mode="ontology_policy",
        contract_pages=22,
        im_pages=32,
    )
    assert len(records) == 30
    assert any(
        r.final_reason_code and r.final_reason_code.startswith("canonical_")
        for r in records
    )


# ── resolve_with_judge (harness+norm 의 judge 적용, 순수 함수) ─────────────────

def test_resolve_with_judge_only_touches_needs_review():
    # needs_review 가 아니면 judge 무시
    assert (
        resolve_with_judge(FinalCheckStatus.EXACT_MATCH, JudgeStatus.DIFFERENT)
        == FinalCheckStatus.EXACT_MATCH
    )


def test_resolve_with_judge_same_and_different():
    assert (
        resolve_with_judge(FinalCheckStatus.NEEDS_REVIEW, JudgeStatus.SAME)
        == FinalCheckStatus.SAME_AFTER_NORMALIZATION
    )
    assert (
        resolve_with_judge(FinalCheckStatus.NEEDS_REVIEW, JudgeStatus.DIFFERENT)
        == FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION
    )


def test_resolve_with_judge_none_keeps_needs_review():
    assert (
        resolve_with_judge(FinalCheckStatus.NEEDS_REVIEW, None)
        == FinalCheckStatus.NEEDS_REVIEW
    )
