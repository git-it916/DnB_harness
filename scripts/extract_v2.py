"""V2 실험 — temp=0, DPI=200 으로 같은 seed 2번 실행.

목적:
1. Vision DPI 200이 이지스블랙 OCR 정확도 개선하나
2. temp=0이 동일 seed에서 완전 결정론인가 (full pipeline 기준)

저장: database/gemma4_v2_t0_d200/
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# DPI 오버라이드 (import 전)
import src.ingest.pdf_to_text as ingest_mod  # noqa: E402
ingest_mod.IMAGE_DPI = 200  # 150 → 200

from src.client.ollama_client import OllamaClient  # noqa: E402
from src.extraction.extractor import extract_from_pdfs  # noqa: E402
from src.guards.base import GuardConfig, GuardContext  # noqa: E402
from src.guards.registry import apply_guards, summarize_events  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("extract_v2")

OUTPUT_DIR = PROJECT_ROOT / "database" / "gemma4_v2_t0_d200"
DATA_DIR = PROJECT_ROOT / "database" / "raw_data"
CONTRACT_PDF = DATA_DIR / "제정신탁계약서_날인본_이지스블랙ON1호_20250722_최종버전.pdf"
IM_PDF = DATA_DIR / "이지스 블랙ON 1호_준감필.pdf"

RUNS = [
    {"label": "run_A_seed42_t0_d200", "seed": 42},
    {"label": "run_B_seed42_t0_d200", "seed": 42},  # 동일 seed → 결정론 확인
]


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"출력: {OUTPUT_DIR}")
    logger.info(f"IMAGE_DPI = {ingest_mod.IMAGE_DPI}")

    for cfg in RUNS:
        run_id = cfg["label"]
        out_dir = OUTPUT_DIR / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        logger.info("=" * 60)
        logger.info(f"[{run_id}] starting")

        try:
            client = OllamaClient(
                model="gemma4:31b",
                seed=cfg["seed"],
                temperature=0.0,
                num_predict=4096,
            )
            client.ping()

            run = extract_from_pdfs(CONTRACT_PDF, IM_PDF, client)
            extraction_json = run.extraction.model_dump_json(indent=2)
            (out_dir / "extraction.json").write_text(extraction_json, encoding="utf-8")

            ctx = GuardContext(
                contract_pdf=CONTRACT_PDF,
                im_pdf=IM_PDF,
                contract_pages=run.contract_pass.pdf_pages,
                im_pages=run.im_pass.pdf_pages,
                config=GuardConfig(g1_format=True, g2_citation=True, g3_constraint=True),
            )
            guarded, events = apply_guards(raw_extraction_json=extraction_json, ctx=ctx)
            guard_log = {
                "run_id": run_id,
                "guard_config": ctx.config.__dict__,
                "events": [ev.model_dump() for ev in events],
                "summary": summarize_events(events),
            }
            (out_dir / "guard_log.json").write_text(
                json.dumps(guard_log, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if guarded is not None:
                (out_dir / "extraction_after_guards.json").write_text(
                    guarded.model_dump_json(indent=2), encoding="utf-8"
                )

            meta = {
                "run_id": run_id,
                "seed": cfg["seed"],
                "temperature": 0.0,
                "image_dpi": ingest_mod.IMAGE_DPI,
                "model": run.model,
                "model_digest": run.model_digest,
                "contract_pdf": CONTRACT_PDF.name,
                "im_pdf": IM_PDF.name,
                "contract_pages": run.contract_pass.pdf_pages,
                "im_pages": run.im_pass.pdf_pages,
                "ollama_contract_pass": run.contract_pass.ollama_meta,
                "ollama_im_pass": run.im_pass.ollama_meta,
                "total_eval_ms": run.total_eval_ms,
                "total_wall_ms": run.total_wall_ms,
                "guard_summary": guard_log["summary"],
            }
            (out_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info(
                f"[{run_id}] DONE | wall={run.total_wall_ms}ms eval={run.total_eval_ms}ms "
                f"events={guard_log['summary']['total_events']} rejected={guard_log['summary']['rejected_count']}"
            )
        except Exception as e:
            logger.error(f"[{run_id}] FAILED: {e}")
            traceback.print_exc()

    return 0


if __name__ == "__main__":
    sys.exit(main())
