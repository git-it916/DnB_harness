"""Baseline 라이브 채점 — LLM 단독으로 골든 30케이스 판정 후 score.json 산출.

3조건의 ① baseline. guard/ontology(결정적)와 같은 골든 입력을 쓰되 하네스 없이
LLM 이 직접 판정한다. 비교용.

실행:
    PYTHONIOENCODING=utf-8 <env>/python.exe scripts/baseline_judge.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.client.ollama_client import OllamaClient  # noqa: E402
from src.scoring.baseline import evaluate_baseline  # noqa: E402
from src.scoring.golden import load_golden_master  # noqa: E402
from src.scoring.scorer import score_cases  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="baseline(LLM 단독) 라이브 채점")
    p.add_argument("--model", default="gemma4:31b")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument(
        "--out", type=Path, default=PROJECT_ROOT / "reports" / "scoring" / "score_baseline.json"
    )
    args = p.parse_args()

    cases = load_golden_master()
    client = OllamaClient(
        model=args.model, seed=args.seed, temperature=args.temperature, num_predict=1024
    )
    print(f"Ollama version: {client.ping()} | 골든 {len(cases)}케이스 판정 시작", flush=True)

    t0 = time.time()
    records = evaluate_baseline(client, cases)
    wall = time.time() - t0

    report = score_cases(records, mode="baseline", golden_version="v0.1", run_id="baseline_live")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    m, c = report["metrics"], report["confusion"]
    print("=" * 60, flush=True)
    print(f"[baseline DONE] {len(cases)}케이스 wall={wall:.0f}s")
    print(
        f"  P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
        f"acc={m['accuracy']:.3f} 환각={m['hallucination_rate']:.3f}"
    )
    print(f"  TP={c['tp']} FP={c['fp']} FN={c['fn']} TN={c['tn']} missing제외={c['missing_excluded']}")
    print(f"  -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
