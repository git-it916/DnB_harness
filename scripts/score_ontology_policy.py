"""ontology_policy_judge scoring: canonical policy first, Claude judge fallback only."""

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
from src.scoring.evaluate import evaluate_golden_ontology_policy_judge  # noqa: E402
from src.scoring.golden import load_golden_master  # noqa: E402
from src.scoring.scorer import score_cases  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ontology_policy_judge scoring")
    parser.add_argument("--contract-pages", type=int, default=22)
    parser.add_argument("--im-pages", type=int, default=32)
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "reports" / "scoring" / "score_ontology_policy_judge.json",
    )
    args = parser.parse_args()

    cases = load_golden_master()
    client = AnthropicJSONClient()
    started = time.time()
    records = evaluate_golden_ontology_policy_judge(
        cases,
        contract_pages=args.contract_pages,
        im_pages=args.im_pages,
        client=client,
    )
    wall = time.time() - started
    report = score_cases(
        records,
        mode="ontology_policy_judge",
        golden_version="v0.1",
        run_id="ontology_policy_judge_live",
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics, confusion = report["metrics"], report["confusion"]
    print(f"[ontology_policy_judge DONE] {len(cases)} cases wall={wall:.0f}s")
    print(
        f"  P={metrics['precision']:.3f} R={metrics['recall']:.3f} "
        f"F1={metrics['f1']:.3f} acc={metrics['accuracy']:.3f} "
        f"hallucination={metrics['hallucination_rate']:.3f}"
    )
    print(
        f"  TP={confusion['tp']} FP={confusion['fp']} FN={confusion['fn']} "
        f"TN={confusion['tn']} missing_excluded={confusion['missing_excluded']}"
    )
    print(f"  -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
