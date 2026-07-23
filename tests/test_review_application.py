from __future__ import annotations

from pathlib import Path

import pytest

from src.application.alias_registry import AliasRegistry
from src.application.review_models import ReviewFieldResult, ReviewResult, summarize_fields
from src.application.review_service import ReviewService
from src.canonical.pipeline import cross_check_with_policy
from src.pipelines.cross_check import CrossCheckValue
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
from src.web_api.store import RunStore


def _value(raw: str | None, role: str) -> DocumentValue:
    return DocumentValue(
        value=None,
        unit=None,
        raw_text=raw,
        citation=Citation(document=role, page=1) if raw else None,
    )


def _field(contract: str | None = None, im: str | None = None) -> ComparableField:
    return ComparableField(
        contract=_value(contract, "신탁계약서"), im=_value(im, "IM")
    )


def _sample_extraction() -> ExtractionResult:
    empty = _field()
    return ExtractionResult(
        schema_version="v0",
        fund=FundExtraction(
            name=_field(
                "이지스블랙 ON 일반사모투자신탁제 1 호", "이지스블랙ON1호"
            ),
            type=empty,
            inception_date=empty,
            maturity_date=empty,
        ),
        party=PartyExtraction(asset_manager=empty, trustee=empty, distributor=empty),
        fee_schedule=FeeScheduleExtraction(
            management_fee=empty, trust_fee=empty, sales_fee=empty
        ),
        redemption_terms=RedemptionTermsExtraction(
            is_redeemable=empty,
            lockup_period=empty,
            redemption_cycle=empty,
            redemption_fee=empty,
        ),
    )


def _store(tmp_path: Path) -> RunStore:
    return RunStore(tmp_path / "dnb.sqlite3", tmp_path / "runs")


def test_approved_alias_resolves_an_uncertain_fund_name(tmp_path):
    store = _store(tmp_path)
    registry = AliasRegistry(store.database_path)
    registry.remember(
        field="fund.name",
        left="이지스블랙 ON 일반사모투자신탁제 1 호",
        right="이지스블랙ON1호",
        source_run_id="seed",
    )
    comparison = next(
        item
        for item in cross_check_with_policy(_sample_extraction())
        if item.field == "fund.name"
    )

    field = ReviewService(alias_lookup=registry)._from_comparison(comparison, [])

    assert field.effective_status == "match"
    assert field.resolution_source == "alias_registry"
    assert field.system_status == "needs_review"


def test_alias_registry_rejects_conflicting_fund_series(tmp_path):
    store = _store(tmp_path)
    registry = AliasRegistry(store.database_path)

    with pytest.raises(ValueError, match="series numbers"):
        registry.remember(
            field="fund.name",
            left="이지스블랙ON 제1호",
            right="이지스블랙ON 제2호",
            source_run_id="seed",
        )


def test_human_decision_overlays_without_erasing_system_status(tmp_path):
    store = _store(tmp_path)
    store.create_run(
        run_id="review_test",
        strategy="ontology_policy",
        model="fake",
        contract_name="contract.pdf",
        im_name="im.pdf",
    )
    field = ReviewFieldResult(
        field="fund.name",
        label="펀드명",
        system_status="needs_review",
        effective_status="needs_human_review",
        resolution_source="unresolved",
        requires_human_review=True,
        reason_code="canonical_not_decisive",
        reason="Needs a human decision.",
        contract=CrossCheckValue(
            raw_text="이지스블랙 ON 일반사모투자신탁제 1 호",
            citation=Citation(document="신탁계약서", page=2),
        ),
        im=CrossCheckValue(
            raw_text="이지스블랙ON1호", citation=Citation(document="IM", page=1)
        ),
    )
    result = ReviewResult(
        run_id="review_test",
        strategy="ontology_policy",
        extraction=_sample_extraction(),
        fields=[field],
        summary=summarize_fields([field]),
        shacl_conforms=True,
        shacl_report_text="Conforms",
        abox_ttl="@prefix dnb: <urn:dnb:> .",
        model="fake",
        model_digest="fake-digest",
        total_latency_ms=10,
        llm_total_tokens=0,
    )
    store.complete("review_test", result)
    store.save_decision(
        run_id="review_test",
        field="fund.name",
        decision="same",
        note="표지 약칭 확인",
        remember_alias=False,
    )

    updated = store.load_result("review_test")

    assert updated is not None
    assert updated.fields[0].system_status == "needs_review"
    assert updated.fields[0].effective_status == "match"
    assert updated.fields[0].resolution_source == "human"
    assert updated.fields[0].human_decision.note == "표지 약칭 확인"
    assert updated.summary.needs_human_review == 0
