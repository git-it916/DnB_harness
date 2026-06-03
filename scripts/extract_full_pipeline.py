"""End-to-end pipeline — PDF → Gemma 추출 → 가드 → ABox+SHACL → cross_check (+옵션 normalize/judge).

PM 의 Gemma 추출 + 가드 (extract_5_runs.py) 와 종현의 온톨로지 + 비교 (run_extract_once.py) 를 한 줄로 합침.

기본: ①+②+③+④cross_check (Gemma + 결정론 가드 + ABox/SHACL + raw 비교). LLM 호출은 Gemma 2번 (추출 contract+IM) 만.
옵션:
    --with-normalize : ④ 정규화 (Claude 호출, ANTHROPIC_API_KEY 필요)
    --with-judge     : ④ LLM Judge (Claude 호출)
    --seeds 42,1,2   : 실행 시드 (기본 42 하나)

실행:
    PYTHONIOENCODING=utf-8 "<env>/python.exe" scripts/extract_full_pipeline.py
    PYTHONIOENCODING=utf-8 "<env>/python.exe" scripts/extract_full_pipeline.py --seeds 42,1,2,3,4 --with-normalize --with-judge

산출: database/gemma4_full/run_NN_seedM/{8개 파일}
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.client.ollama_client import OllamaClient  # noqa: E402
from src.extraction.extractor import extract_from_pdfs  # noqa: E402
from src.guards.base import GuardConfig, GuardContext  # noqa: E402
from src.guards.registry import apply_guards, summarize_events  # noqa: E402
from src.ontology.mapping import extraction_to_graph  # noqa: E402
from src.ontology.validate import validate_graph  # noqa: E402
from src.pipelines.cross_check import (  # noqa: E402
    apply_normalization_to_cross_check,
    cross_check_extraction,
)
from src.schemas.extraction import ExtractionResult  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("full_pipeline")

DATA_DIR = PROJECT_ROOT / "database" / "raw_data"
CONTRACT_PDF = DATA_DIR / "제정신탁계약서_날인본_이지스블랙ON1호_20250722_최종버전.pdf"
IM_PDF = DATA_DIR / "이지스 블랙ON 1호_준감필.pdf"
DEFAULT_OUTPUT = PROJECT_ROOT / "database" / "gemma4_full"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Full Gemma + Guards + Ontology + Compare pipeline.")
    p.add_argument("--contract-pdf", type=Path, default=CONTRACT_PDF)
    p.add_argument("--im-pdf", type=Path, default=IM_PDF)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--seeds", default="42", help="콤마 구분 (예: 42,1,2,3,4)")
    p.add_argument("--model", default="gemma4:31b")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--with-normalize", action="store_true", help="Claude 정규화 호출 (API key 필요)")
    p.add_argument("--with-judge", action="store_true", help="Claude LLM Judge 호출")
    return p.parse_args()


def run_one_seed(
    *,
    seed: int,
    args: argparse.Namespace,
    out_dir: Path,
) -> dict:
    """seed 1개에 대한 풀 파이프라인. 산출물 8종 폴더에 저장."""
    out_dir.mkdir(parents=True, exist_ok=True)
    wall_start = time.time()

    # ① 추출 (Gemma) ──────────────────────────────────────────
    client = OllamaClient(
        model=args.model,
        seed=seed,
        temperature=args.temperature,
        num_predict=4096,
    )
    client.ping()
    run = extract_from_pdfs(args.contract_pdf, args.im_pdf, client)
    extraction_raw_json = run.extraction.model_dump_json(indent=2)
    (out_dir / "extraction.json").write_text(extraction_raw_json, encoding="utf-8")
    logger.info(
        f"[seed={seed}] ① 추출 끝 — contract={run.contract_pass.pdf_pages}p im={run.im_pass.pdf_pages}p "
        f"eval_ms={run.total_eval_ms}"
    )

    # ② 가드 3종 ─────────────────────────────────────────────
    ctx = GuardContext(
        contract_pdf=args.contract_pdf,
        im_pdf=args.im_pdf,
        contract_pages=run.contract_pass.pdf_pages,
        im_pages=run.im_pass.pdf_pages,
        config=GuardConfig(g1_format=True, g2_citation=True, g3_constraint=True),
    )
    guarded, events = apply_guards(raw_extraction_json=extraction_raw_json, ctx=ctx)
    guard_summary = summarize_events(events)
    guard_log = {
        "run_id": out_dir.name,
        "guard_config": ctx.config.__dict__,
        "events": [ev.model_dump() for ev in events],
        "summary": guard_summary,
    }
    (out_dir / "guard_log.json").write_text(
        json.dumps(guard_log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if guarded is None:
        logger.error(f"[seed={seed}] ② 가드 G1 실패 — 이후 단계 스킵")
        return {"seed": seed, "fatal": True, "wall_ms": int((time.time() - wall_start) * 1000)}
    (out_dir / "extraction_after_guards.json").write_text(
        guarded.model_dump_json(indent=2), encoding="utf-8"
    )
    logger.info(
        f"[seed={seed}] ② 가드 끝 — events={guard_summary['total_events']} rejected={guard_summary['rejected_count']}"
    )

    # ③ 온톨로지 + SHACL ─────────────────────────────────────
    graph = extraction_to_graph(guarded)
    (out_dir / "abox.ttl").write_text(graph.serialize(format="turtle"), encoding="utf-8")
    validation = validate_graph(graph)
    (out_dir / "shacl_report.txt").write_text(validation.report_text, encoding="utf-8")
    (out_dir / "shacl_validation.json").write_text(
        json.dumps({"conforms": validation.conforms}, indent=2), encoding="utf-8"
    )
    logger.info(
        f"[seed={seed}] ③ 온톨로지 끝 — triples={len(graph)} conforms={validation.conforms}"
    )

    # ④ cross_check (+옵션 normalize, judge) ─────────────────
    cc_results = cross_check_extraction(guarded)

    norm_results = None
    if args.with_normalize:
        from src.pipelines.normalize import normalize_extraction  # noqa: E402

        norm_results = normalize_extraction(guarded)
        cc_results = apply_normalization_to_cross_check(cc_results, norm_results)
        (out_dir / "normalization.json").write_text(
            json.dumps(
                [r.model_dump(mode="json") for r in norm_results],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info(f"[seed={seed}] ④ normalize 끝 — {len(norm_results)} fields")

    judgements = []
    if args.with_judge:
        from src.pipelines.llm_judge import judge_needs_review  # noqa: E402

        judgements = judge_needs_review(cc_results)
        (out_dir / "llm_judgements.json").write_text(
            json.dumps(
                [j.model_dump(mode="json") for j in judgements],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info(f"[seed={seed}] ④ judge 끝 — {len(judgements)} judgements")

    (out_dir / "cross_check.json").write_text(
        json.dumps(
            [r.model_dump(mode="json") for r in cc_results],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # 진단 한 줄 요약
    by_status: dict[str, int] = {}
    for r in cc_results:
        key = r.final_status or r.status
        by_status[str(key)] = by_status.get(str(key), 0) + 1
    logger.info(
        f"[seed={seed}] ④ cross_check 끝 — "
        + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
    )

    # 메타 ────────────────────────────────────────────────
    total_wall = int((time.time() - wall_start) * 1000)
    meta = {
        "run_id": out_dir.name,
        "seed": seed,
        "model": args.model,
        "model_digest": run.model_digest,
        "temperature": args.temperature,
        "with_normalize": args.with_normalize,
        "with_judge": args.with_judge,
        "contract_pdf": args.contract_pdf.name,
        "im_pdf": args.im_pdf.name,
        "contract_pages": run.contract_pass.pdf_pages,
        "im_pages": run.im_pass.pdf_pages,
        "contract_sha256": run.contract_pass.pdf_sha256,
        "im_sha256": run.im_pass.pdf_sha256,
        "guard_summary": guard_summary,
        "shacl_conforms": validation.conforms,
        "cross_check_by_status": by_status,
        "total_eval_ms": run.total_eval_ms,
        "total_wall_ms": total_wall,
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"[seed={seed}] DONE → {out_dir} (wall={total_wall}ms)")
    return meta


def main() -> int:
    args = parse_args()
    if not args.contract_pdf.exists():
        logger.error(f"계약서 PDF 없음: {args.contract_pdf}")
        return 1
    if not args.im_pdf.exists():
        logger.error(f"IM PDF 없음: {args.im_pdf}")
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"출력 디렉토리: {args.output_dir}")

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    logger.info(
        f"seeds={seeds} model={args.model} temp={args.temperature} "
        f"normalize={args.with_normalize} judge={args.with_judge}"
    )

    all_meta = []
    for idx, seed in enumerate(seeds, start=1):
        run_id = f"run_{idx:02d}_seed{seed}"
        out_dir = args.output_dir / run_id
        logger.info("=" * 60)
        try:
            meta = run_one_seed(seed=seed, args=args, out_dir=out_dir)
            all_meta.append(meta)
        except Exception as e:
            logger.error(f"[{run_id}] FAILED: {e}")
            traceback.print_exc()
            (out_dir / "error.txt").write_text(
                f"{e}\n\n{traceback.format_exc()}", encoding="utf-8"
            )

    # 전체 요약
    summary_path = args.output_dir / "pipeline_summary.json"
    summary_path.write_text(
        json.dumps(
            {"runs": all_meta, "n_runs": len(all_meta), "seeds": seeds},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info(f"전체 요약 → {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
