"""5회 추출 + 가드 적용 후 database/gemma4/ 에 저장.

- 동일 PDF 두 개 (계약서 + IM)
- 5가지 seed (결정론·변동성 비교용)
- 각 run 마다: extraction.json + guard_log.json + meta.json 저장

실행:
    PYTHONIOENCODING=utf-8 "<env>/python.exe" scripts/extract_5_runs.py
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.client.ollama_client import OllamaClient  # noqa: E402
from src.extraction.extractor import extract_from_pdfs  # noqa: E402
from src.guards.base import GuardConfig, GuardContext  # noqa: E402
from src.guards.registry import apply_guards, summarize_events  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("extract_5_runs")

OUTPUT_DIR = PROJECT_ROOT / "database" / "gemma4"
DATA_DIR = PROJECT_ROOT / "database" / "raw_data"

CONTRACT_PDF = DATA_DIR / "제정신탁계약서_날인본_이지스블랙ON1호_20250722_최종버전.pdf"
IM_PDF = DATA_DIR / "이지스 블랙ON 1호_준감필.pdf"

SEEDS = [42, 1, 2, 3, 4]  # 5 runs


def main() -> int:
    if not CONTRACT_PDF.exists():
        logger.error(f"계약서 PDF 없음: {CONTRACT_PDF}")
        return 1
    if not IM_PDF.exists():
        logger.error(f"IM PDF 없음: {IM_PDF}")
        return 1
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"출력 디렉토리: {OUTPUT_DIR}")

    # 가드 ON 풀로
    guard_ctx_kwargs = {
        "contract_pdf": CONTRACT_PDF,
        "im_pdf": IM_PDF,
        "config": GuardConfig(g1_format=True, g2_citation=True, g3_constraint=True),
    }

    for idx, seed in enumerate(SEEDS, start=1):
        run_id = f"run_{idx:02d}_seed{seed}"
        out_dir = OUTPUT_DIR / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 60)
        logger.info(f"[{run_id}] starting")
        try:
            client = OllamaClient(
                model="gemma4:31b",
                seed=seed,
                temperature=0.0,  # V2 채택 (§13.7) — temp=0 안전 검증됨
                num_predict=4096,
            )
            client.ping()

            # 1) 추출
            run = extract_from_pdfs(CONTRACT_PDF, IM_PDF, client)
            extraction_raw_json = run.extraction.model_dump_json(indent=2)
            (out_dir / "extraction.json").write_text(extraction_raw_json, encoding="utf-8")
            logger.info(
                f"[{run_id}] extraction saved | "
                f"contract_pages={run.contract_pass.pdf_pages} "
                f"im_pages={run.im_pass.pdf_pages} "
                f"eval_ms={run.total_eval_ms} wall_ms={run.total_wall_ms}"
            )

            # 2) 가드
            ctx = GuardContext(
                contract_pages=run.contract_pass.pdf_pages,
                im_pages=run.im_pass.pdf_pages,
                **guard_ctx_kwargs,
            )
            guarded_extraction, events = apply_guards(
                raw_extraction_json=extraction_raw_json,
                ctx=ctx,
                retry_callback=None,
            )
            guard_log = {
                "run_id": run_id,
                "guard_config": ctx.config.__dict__,
                "events": [ev.model_dump() for ev in events],
                "summary": summarize_events(events),
            }
            (out_dir / "guard_log.json").write_text(
                json.dumps(guard_log, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if guarded_extraction is not None:
                (out_dir / "extraction_after_guards.json").write_text(
                    guarded_extraction.model_dump_json(indent=2), encoding="utf-8"
                )
            logger.info(
                f"[{run_id}] guards done | "
                f"events={len(events)} rejected={guard_log['summary']['rejected_count']}"
            )

            # 3) 메타
            meta = {
                "run_id": run_id,
                "seed": seed,
                "model": run.model,
                "model_digest": run.model_digest,
                "temperature": run.temperature,
                "contract_pdf": str(CONTRACT_PDF.name),
                "contract_sha256": run.contract_pass.pdf_sha256,
                "contract_pages": run.contract_pass.pdf_pages,
                "im_pdf": str(IM_PDF.name),
                "im_sha256": run.im_pass.pdf_sha256,
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
            logger.info(f"[{run_id}] DONE → {out_dir}")
        except Exception as e:
            logger.error(f"[{run_id}] FAILED: {e}")
            traceback.print_exc()
            (out_dir / "error.txt").write_text(
                f"{e}\n\n{traceback.format_exc()}", encoding="utf-8"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
