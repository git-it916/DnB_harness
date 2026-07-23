"""Operational PDF review service: extract -> guard -> policy -> selective judge."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from src.application.review_models import (
    JudgeSuggestion,
    ReviewFieldResult,
    ReviewResult,
    summarize_fields,
)
from src.canonical.pipeline import cross_check_with_policy
from src.client.anthropic_client import AnthropicJSONClient
from src.guards.base import GuardConfig, GuardContext
from src.guards.registry import apply_guards
from src.ontology.mapping import extraction_to_graph
from src.ontology.validate import validate_graph
from src.pipelines.cross_check import CrossCheckResult, FinalCheckStatus
from src.pipelines.extract import DocumentInput, extract_from_documents
from src.pipelines.llm_judge import (
    JudgeStatus,
    judge_maturity,
    judge_needs_review,
    judge_redemption_fee,
    judge_redeemability,
    resolve_maturity_judgement,
    resolve_redemption_fee_judgement,
    resolve_redeemability_judgement,
)
from src.schemas.extraction import ExtractionResult

ProgressCallback = Callable[[str], None]


class AliasLookup(Protocol):
    def matches(self, field: str, left: str | None, right: str | None) -> bool: ...


class ReviewService:
    """Runs the production-shaped Tier 1/Tier 2 path for arbitrary PDFs."""

    def __init__(
        self,
        *,
        extraction_client: AnthropicJSONClient | None = None,
        judge_client=None,
        alias_lookup: AliasLookup | None = None,
    ) -> None:
        self.extraction_client = extraction_client
        self.judge_client = judge_client
        self.alias_lookup = alias_lookup

    def run(
        self,
        *,
        run_id: str,
        contract_pdf: Path,
        im_pdf: Path,
        strategy: str = "ontology_policy_judge",
        progress: ProgressCallback | None = None,
    ) -> ReviewResult:
        if strategy not in ("ontology_policy", "ontology_policy_judge"):
            raise ValueError(f"unsupported review strategy: {strategy}")
        emit = progress or (lambda _stage: None)
        started = time.perf_counter()

        extraction_client = self.extraction_client or AnthropicJSONClient(max_tokens=8192)
        if self.judge_client is None:
            self.judge_client = extraction_client

        emit("extracting_documents")
        extraction = extract_from_documents(
            [
                DocumentInput(role="신탁계약서", path=contract_pdf),
                DocumentInput(role="IM", path=im_pdf),
            ],
            llm=extraction_client,
            system_prompt_path=(
                Path(__file__).resolve().parents[2]
                / "prompts"
                / "v0"
                / "extract"
                / "system.md"
            ),
        )
        result = self.review_extraction(
            run_id=run_id,
            extraction=extraction,
            contract_pdf=contract_pdf,
            im_pdf=im_pdf,
            contract_pages=len(PdfReader(contract_pdf).pages),
            im_pages=len(PdfReader(im_pdf).pages),
            strategy=strategy,
            model=extraction_client.model,
            model_digest="unavailable",
            total_latency_ms=0,
            llm_total_tokens=0,
            progress=emit,
        )
        return result.model_copy(
            update={
                "total_latency_ms": int((time.perf_counter() - started) * 1000),
                "llm_total_tokens": _total_anthropic_tokens(extraction_client),
            }
        )

    def review_extraction(
        self,
        *,
        run_id: str,
        extraction: ExtractionResult,
        contract_pdf: Path,
        im_pdf: Path,
        contract_pages: int,
        im_pages: int,
        strategy: str = "ontology_policy_judge",
        model: str = "precomputed",
        model_digest: str = "precomputed",
        total_latency_ms: int = 0,
        llm_total_tokens: int = 0,
        progress: ProgressCallback | None = None,
    ) -> ReviewResult:
        """Review a precomputed extraction without rerunning the extraction model."""
        if strategy not in ("ontology_policy", "ontology_policy_judge"):
            raise ValueError(f"unsupported review strategy: {strategy}")
        emit = progress or (lambda _stage: None)

        emit("applying_guards")
        ctx = GuardContext(
            contract_pdf=contract_pdf,
            im_pdf=im_pdf,
            contract_pages=contract_pages,
            im_pages=im_pages,
            config=GuardConfig(g1_format=True, g2_citation=True, g3_constraint=True),
        )
        guarded, guard_events = apply_guards(
            raw_extraction_json=extraction.model_dump_json(), ctx=ctx
        )
        if guarded is None:
            raise RuntimeError("G1 format guard rejected the extraction result")

        emit("comparing_policy")
        comparisons = cross_check_with_policy(guarded)

        emit("resolving_aliases")
        fields = [self._from_comparison(result, guard_events) for result in comparisons]

        if strategy == "ontology_policy_judge":
            emit("selective_judge")
            fields = self._apply_selective_judge(fields, comparisons, guarded)

        emit("building_audit")
        graph = extraction_to_graph(guarded)
        validation = validate_graph(graph)
        return ReviewResult(
            run_id=run_id,
            strategy=strategy,
            extraction=guarded,
            fields=fields,
            summary=summarize_fields(fields),
            guard_log=guard_events,
            shacl_conforms=validation.conforms,
            shacl_report_text=validation.report_text,
            abox_ttl=graph.serialize(format="turtle"),
            model=model,
            model_digest=model_digest,
            total_latency_ms=total_latency_ms,
            llm_total_tokens=llm_total_tokens,
        )

    def _from_comparison(self, result: CrossCheckResult, guard_events) -> ReviewFieldResult:
        if self.alias_lookup and self.alias_lookup.matches(
            result.field, result.contract.raw_text, result.im.raw_text
        ):
            status = "match"
            source = "alias_registry"
            requires_human = False
            reason_code = "approved_alias_match"
            reason = "An explicitly approved alias pair matched this evidence."
        else:
            status, source = _effective_status(result.final_status)
            requires_human = status == "needs_human_review"
            reason_code = result.final_reason_code or "unknown"
            reason = result.final_reason or "No reason was recorded."
        related_events = [
            event
            for event in guard_events
            if event.field_path
            and (
                event.field_path == result.field
                or event.field_path.startswith(result.field + ".")
            )
        ]
        return ReviewFieldResult(
            field=result.field,
            label=result.label,
            system_status=str(result.final_status),
            effective_status=status,
            resolution_source=source,
            requires_human_review=requires_human,
            reason_code=reason_code,
            reason=reason,
            contract=result.contract,
            im=result.im,
            canonical=result.canonical,
            guard_events=related_events,
        )

    def _apply_selective_judge(self, fields, comparisons, extraction):
        client = self.judge_client
        if client is None:
            try:
                client = AnthropicJSONClient()
            except ValueError:
                return fields
        by_comparison = {item.field: item for item in comparisons}
        output: list[ReviewFieldResult] = []
        for field in fields:
            comparison = by_comparison[field.field]
            judge_allowed = bool((comparison.canonical or {}).get("judge_allowed"))
            if not field.requires_human_review or not judge_allowed:
                output.append(field)
                continue
            resolved: JudgeStatus | None = None
            suggestion: JudgeSuggestion | None = None
            try:
                if field.field == "redemption_terms.is_redeemable":
                    judgement = judge_redeemability(comparison, llm=client)
                    resolved = resolve_redeemability_judgement(judgement)
                elif field.field == "fund.maturity_date":
                    judgement = judge_maturity(
                        comparison,
                        contract_inception_raw=extraction.fund.inception_date.contract.raw_text,
                        im_inception_raw=extraction.fund.inception_date.im.raw_text,
                        llm=client,
                    )
                    resolved = resolve_maturity_judgement(judgement)
                elif field.field == "redemption_terms.redemption_fee":
                    judgement = judge_redemption_fee(comparison, llm=client)
                    resolved = resolve_redemption_fee_judgement(judgement)
                else:
                    judgements = judge_needs_review([comparison], llm=client)
                    if judgements:
                        judgement = judgements[0]
                        resolved = judgement.status
            except Exception:  # provider/network failures fall back to human review
                # A judge failure must not discard deterministic review output.
                # The unresolved field remains assigned to a human reviewer.
                output.append(field)
                continue

            if resolved is None:
                output.append(field.model_copy(update={"judge_suggestion": suggestion}))
                continue
            effective = "match" if resolved == JudgeStatus.SAME else "mismatch"
            reason_code = (
                "specialized_high_confidence_judge"
                if field.field
                in {
                    "redemption_terms.is_redeemable",
                    "fund.maturity_date",
                    "redemption_terms.redemption_fee",
                }
                else "llm_judge_classification"
            )
            output.append(
                field.model_copy(
                    update={
                        "effective_status": effective,
                        "resolution_source": "llm_judge",
                        "requires_human_review": False,
                        "reason_code": reason_code,
                        "reason": "The LLM Judge classified the two extracted evidence snippets.",
                    }
                )
            )
        return output


def _total_anthropic_tokens(client: AnthropicJSONClient) -> int:
    usage = getattr(client, "last_usage", {})
    return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))


def _effective_status(final_status) -> tuple[str, str]:
    if final_status in (
        FinalCheckStatus.EXACT_MATCH,
        FinalCheckStatus.SAME_AFTER_NORMALIZATION,
    ):
        return "match", "deterministic"
    if final_status == FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION:
        return "mismatch", "deterministic"
    if final_status == FinalCheckStatus.MISSING_EVIDENCE:
        return "missing_evidence", "unresolved"
    return "needs_human_review", "unresolved"
