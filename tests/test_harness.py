"""Stage C 하네스 러너 테스트 (TDD, LLM 불필요 — 결정적 핵심만)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.guards.base import GuardConfig, GuardContext
from src.harness.manifest import build_manifest
from src.harness.pipeline import build_harness_result, guard_config_for
from src.schemas.extraction import (
    Citation,
    ComparableField,
    DocumentValue,
    ExtractionResult,
    FeeScheduleExtraction,
    FundExtraction,
    PartyExtraction,
    RedemptionTermsExtraction,
)


def _v(raw: str | None = None, page: int = 1, role: str = "신탁계약서") -> DocumentValue:
    if raw is None:
        return DocumentValue(value=None, unit=None, raw_text=None, citation=None)
    return DocumentValue(
        value=None, unit=None, raw_text=raw, citation=Citation(document=role, page=page)
    )


def _cf(c: str | None = None, i: str | None = None, cp: int = 1, ip: int = 1) -> ComparableField:
    return ComparableField(contract=_v(c, cp, "신탁계약서"), im=_v(i, ip, "IM"))


def _sample_extraction() -> ExtractionResult:
    empty = _cf()
    return ExtractionResult(
        schema_version="v0",
        fund=FundExtraction(
            name=_cf("이지스블랙ON 일반사모투자신탁제1호", "이지스블랙ON 일반사모투자신탁제1호", 2, 9),
            type=empty,
            inception_date=empty,
            maturity_date=empty,
        ),
        party=PartyExtraction(asset_manager=empty, trustee=empty, distributor=empty),
        fee_schedule=FeeScheduleExtraction(
            management_fee=_cf("연 1,000분의 8.9", "[운용] 연[ 0.89 ] %", 15, 9),
            trust_fee=empty,
            sales_fee=empty,
        ),
        redemption_terms=RedemptionTermsExtraction(
            is_redeemable=empty, lockup_period=empty, redemption_cycle=empty, redemption_fee=empty
        ),
    )


def _ctx() -> GuardContext:
    return GuardContext(
        contract_pdf=Path("c.pdf"),
        im_pdf=Path("i.pdf"),
        contract_pages=22,
        im_pages=32,
        config=guard_config_for("guard"),
    )


def test_baseline_mode_has_only_extraction():
    r = build_harness_result(_sample_extraction(), mode="baseline")
    assert r.mode == "baseline"
    assert r.cross_check is None
    assert r.abox_ttl is None
    assert r.shacl_conforms is None
    assert r.guard_log == []


def test_ontology_mode_runs_abox_shacl_crosscheck_without_guards():
    r = build_harness_result(_sample_extraction(), mode="ontology")
    assert r.guard_log == []
    assert r.cross_check is not None and len(r.cross_check) == 14
    assert r.abox_ttl and "@prefix" in r.abox_ttl
    assert isinstance(r.shacl_conforms, bool)


def test_guard_mode_records_guard_events():
    r = build_harness_result(
        _sample_extraction(), mode="guard", ctx=_ctx()
    )
    assert len(r.guard_log) > 0  # G1/G2/G3 이벤트 존재
    assert r.cross_check is not None and len(r.cross_check) == 14
    assert {e.guard for e in r.guard_log} <= {"G1", "G2", "G3"}


def test_guard_mode_requires_ctx():
    with pytest.raises(ValueError):
        build_harness_result(_sample_extraction(), mode="guard")


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        build_harness_result(_sample_extraction(), mode="nonsense")


def test_build_manifest_has_required_keys():
    manifest = build_manifest(
        run_id="exp_guard_test",
        mode="guard",
        guard_config=GuardConfig(g1_format=True, g2_citation=True, g3_constraint=True),
        backend={"name": "gemma4:31b", "seed": 42},
        inputs={"contract_pages": 22, "im_pages": 32},
        started_at="2026-06-03T00:00:00Z",
        ended_at="2026-06-03T00:03:00Z",
        total_latency_s=180.0,
        llm_call_count=2,
        llm_total_tokens=18000,
    )
    for key in ("schema_version", "run_id", "mode", "guards", "backend", "inputs",
                "started_at", "ended_at", "total_latency_s", "llm_call_count"):
        assert key in manifest
    assert manifest["guards"]["g1_format"] is True
    assert manifest["cost_usd"] == 0.0
