"""3조건 하네스 러너.

- build_harness_result : 이미 추출된 ExtractionResult → HarnessResult (결정적, LLM 불필요).
- run_harness         : LLM 추출까지 포함한 풀 실행 (Ollama 필요).
"""

from __future__ import annotations

from pathlib import Path

from src.client.ollama_client import OllamaClient
from src.extraction.extractor import ExtractionRun, extract_from_pdfs
from src.guards.base import GuardConfig, GuardContext
from src.guards.registry import apply_guards
from src.harness.result import HarnessMode, HarnessResult
from src.ontology.mapping import extraction_to_graph
from src.ontology.validate import validate_graph
from src.pipelines.cross_check import cross_check_extraction
from src.schemas.extraction import ExtractionResult

_VALID_MODES = ("baseline", "ontology", "guard")


def guard_config_for(mode: HarnessMode) -> GuardConfig:
    """모드별 가드 토글 (INTERFACES.md §3)."""
    if mode == "guard":
        return GuardConfig(g1_format=True, g2_citation=True, g3_constraint=True)
    # baseline / ontology : 가드 미집행
    return GuardConfig(g1_format=False, g2_citation=False, g3_constraint=False)


def build_harness_result(
    extraction: ExtractionResult,
    *,
    mode: HarnessMode,
    ctx: GuardContext | None = None,
    raw_extraction_json: str | None = None,
    total_latency_ms: int = 0,
    llm_call_count: int = 0,
    llm_total_tokens: int = 0,
    llm_total_cost_usd: float = 0.0,
) -> HarnessResult:
    """추출 결과 → 모드별 HarnessResult (결정적).

    Raises:
        ValueError: mode 가 유효하지 않거나, guard 모드인데 ctx 가 없을 때.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode '{mode}' (valid: {_VALID_MODES})")

    meta = dict(
        total_latency_ms=total_latency_ms,
        llm_call_count=llm_call_count,
        llm_total_tokens=llm_total_tokens,
        llm_total_cost_usd=llm_total_cost_usd,
    )

    # baseline: 자유 추출만, 진단/집행 없음
    if mode == "baseline":
        return HarnessResult(mode=mode, extraction=extraction, **meta)

    guard_log = []
    effective = extraction

    if mode == "guard":
        if ctx is None:
            raise ValueError("guard mode requires a GuardContext")
        raw = raw_extraction_json or extraction.model_dump_json()
        guarded, guard_log = apply_guards(raw_extraction_json=raw, ctx=ctx)
        if guarded is None:
            # G1 치명 실패 — JSON 파싱 불가라 ABox/cross_check 자체가 불가능.
            # baseline(cross_check=None)과 구분되도록 g1_fatal 플래그를 세운다.
            return HarnessResult(
                mode=mode,
                extraction=extraction,
                guard_log=guard_log,
                g1_fatal=True,
                **meta,
            )
        effective = guarded

    # ontology / guard 공통: ABox + SHACL + cross_check
    graph = extraction_to_graph(effective)
    validation = validate_graph(graph)
    cross_check = cross_check_extraction(effective)

    return HarnessResult(
        mode=mode,
        extraction=effective,
        guard_log=guard_log,
        abox_ttl=graph.serialize(format="turtle"),
        shacl_conforms=validation.conforms,
        shacl_report_text=validation.report_text,
        cross_check=cross_check,
        **meta,
    )


def run_harness(
    client: OllamaClient,
    contract_pdf: Path,
    im_pdf: Path,
    *,
    mode: HarnessMode,
) -> tuple[HarnessResult, ExtractionRun]:
    """LLM 추출 → HarnessResult 풀 실행 (Ollama 필요).

    Returns:
        (HarnessResult, ExtractionRun) — manifest 작성에 ExtractionRun 메타 사용.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode '{mode}' (valid: {_VALID_MODES})")

    run = extract_from_pdfs(contract_pdf, im_pdf, client)

    ctx = None
    if mode == "guard":
        ctx = GuardContext(
            contract_pdf=contract_pdf,
            im_pdf=im_pdf,
            contract_pages=run.contract_pass.pdf_pages,
            im_pages=run.im_pass.pdf_pages,
            config=guard_config_for(mode),
        )

    llm_tokens = sum(
        p.ollama_meta.get("prompt_eval_count", 0) + p.ollama_meta.get("eval_count", 0)
        for p in (run.contract_pass, run.im_pass)
    )

    result = build_harness_result(
        run.extraction,
        mode=mode,
        ctx=ctx,
        total_latency_ms=run.total_wall_ms,
        llm_call_count=2,  # contract + im 2-pass
        llm_total_tokens=llm_tokens,
        llm_total_cost_usd=0.0,  # 로컬 모델 비용 0
    )
    return result, run
