"""Baseline 판정 매핑/파싱 테스트 (LLM 불필요 부분만)."""

from __future__ import annotations

from src.pipelines.cross_check import FinalCheckStatus
from src.scoring.baseline import BaselineVerdict, _parse_verdict, verdict_to_final_status


def test_verdict_to_final_status_mapping():
    assert verdict_to_final_status("match") == FinalCheckStatus.EXACT_MATCH
    assert verdict_to_final_status("mismatch") == FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION
    assert verdict_to_final_status("missing") == FinalCheckStatus.MISSING_EVIDENCE


def test_parse_verdict_reads_clean_json():
    assert _parse_verdict('{"verdict": "mismatch", "reason": "다름"}') == BaselineVerdict.MISMATCH


def test_parse_verdict_keyword_fallback_on_bad_json():
    assert _parse_verdict("the answer is mismatch because ...") == BaselineVerdict.MISMATCH


def test_parse_verdict_defaults_missing_when_unreadable():
    assert _parse_verdict("@@@unparseable@@@") == BaselineVerdict.MISSING
