"""harness+normalization+judge 라이브 채점 (3번째 조건). Claude 필요.

guard(결정적) + normalize(Claude) + judge(Claude)로 골든 30케이스를 채점한다.
non-harness(baseline) / harness(guard) 와 비교용.

실행:
    PYTHONIOENCODING=utf-8 <env>/python.exe scripts/score_harness_norm.py
필요: .env 의 ANTHROPIC_API_KEY
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from src.client.anthropic_client import AnthropicJSONClient  # noqa: E402
from src.scoring.evaluate import evaluate_golden_full  # noqa: E402
from src.scoring.golden import load_golden_master  # noqa: E402
from src.scoring.scorer import score_cases  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="harness+norm+judge 라이브 채점")
    p.add_argument("--contract-pages", type=int, default=22)
    p.add_argument("--im-pages", type=int, default=32)
    p.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "reports" / "scoring" / "score_harness_norm.json",
    )
    args = p.parse_args()

    cases = load_golden_master()
    client = AnthropicJSONClient()
    print(f"Claude 정규화+judge 시작 | 골든 {len(cases)}케이스", flush=True)

    t0 = time.time()
    records = evaluate_golden_full(
        cases, contract_pages=args.contract_pages, im_pages=args.im_pages, client=client
    )
    wall = time.time() - t0

    report = score_cases(
        records, mode="harness_norm_judge", golden_version="v0.2", run_id="vf_0607"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    m, c = report["metrics"], report["confusion"]
    print("=" * 60, flush=True)
    print(f"[harness+norm DONE] {len(cases)}케이스 wall={wall:.0f}s")
    print(
        f"  P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
        f"acc={m['accuracy']:.3f} 환각={m['hallucination_rate']:.3f}"
    )
    print(f"  TP={c['tp']} FP={c['fp']} FN={c['fn']} TN={c['tn']} missing제외={c['missing_excluded']}")
    print(f"  -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
