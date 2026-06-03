"""단일 모드 하네스 라이브 실행 — run_harness 로 LLM 추출부터 검증까지.

src/harness 러너의 얇은 진입점. 산출물(HarnessResult JSON + manifest)을 저장한다.

실행:
    PYTHONIOENCODING=utf-8 <env>/python.exe scripts/harness_run.py --mode guard
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.client.ollama_client import OllamaClient  # noqa: E402
from src.harness.manifest import build_manifest  # noqa: E402
from src.harness.pipeline import guard_config_for, run_harness  # noqa: E402

DATA_DIR = PROJECT_ROOT / "database" / "raw_data"
CONTRACT_PDF = DATA_DIR / "제정신탁계약서_날인본_이지스블랙ON1호_20250722_최종버전.pdf"
IM_PDF = DATA_DIR / "이지스 블랙ON 1호_준감필.pdf"
DEFAULT_OUT = PROJECT_ROOT / "database" / "gemma4_harness"


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    p = argparse.ArgumentParser(description="단일 모드 하네스 라이브 실행")
    p.add_argument("--mode", default="guard", choices=["baseline", "ontology", "guard"])
    p.add_argument("--model", default="gemma4:31b")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--contract-pdf", type=Path, default=CONTRACT_PDF)
    p.add_argument("--im-pdf", type=Path, default=IM_PDF)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    if not args.contract_pdf.exists() or not args.im_pdf.exists():
        print(f"PDF 없음: {args.contract_pdf} / {args.im_pdf}", file=sys.stderr)
        return 1

    out_dir = args.output_dir / f"run_live_{args.mode}_seed{args.seed}"
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OllamaClient(
        model=args.model, seed=args.seed, temperature=args.temperature, num_predict=4096
    )
    print(f"Ollama version: {client.ping()}", flush=True)

    started = _iso_now()
    wall0 = time.time()
    result, run = run_harness(client, args.contract_pdf, args.im_pdf, mode=args.mode)
    wall_s = time.time() - wall0
    ended = _iso_now()

    # 산출물 저장
    (out_dir / "harness_result.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    if result.abox_ttl:
        (out_dir / "abox.ttl").write_text(result.abox_ttl, encoding="utf-8")
    if result.shacl_report_text:
        (out_dir / "shacl_report.txt").write_text(result.shacl_report_text, encoding="utf-8")

    manifest = build_manifest(
        run_id=out_dir.name,
        mode=args.mode,
        guard_config=guard_config_for(args.mode),
        backend={
            "name": run.model,
            "model_id": run.model_digest,
            "seed": run.seed,
            "temperature": run.temperature,
        },
        inputs={
            "contract_pdf": args.contract_pdf.name,
            "contract_pages": run.contract_pass.pdf_pages,
            "contract_sha256": run.contract_pass.pdf_sha256,
            "im_pdf": args.im_pdf.name,
            "im_pages": run.im_pass.pdf_pages,
            "im_sha256": run.im_pass.pdf_sha256,
        },
        started_at=started,
        ended_at=ended,
        total_latency_s=wall_s,
        llm_call_count=result.llm_call_count,
        llm_total_tokens=result.llm_total_tokens,
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 콘솔 요약
    cc = result.cross_check or []
    by_status: dict[str, int] = {}
    for r in cc:
        key = str(r.final_status)
        by_status[key] = by_status.get(key, 0) + 1
    rejects = [e for e in result.guard_log if e.decision.value == "reject"]

    print("=" * 60, flush=True)
    print(f"[DONE] mode={args.mode} wall={wall_s:.0f}s tokens={result.llm_total_tokens}")
    print(f"  guard_events={len(result.guard_log)} rejects={len(rejects)}")
    print(f"  shacl_conforms={result.shacl_conforms}")
    print(f"  cross_check by_status={by_status}")
    print(f"  -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
