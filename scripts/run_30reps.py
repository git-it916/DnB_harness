"""3-tier × 30-reps 실험 러너 (database/gemma4_30reps).

tier1 = ontology_policy        (LLM 없음, 결정적)        — 30 reps 동일(분산 0)
tier2 = ontology_policy_judge  (결정적 + 선택적 judge)   — Claude judge fallback
tier3 = harness_norm_judge     (LLM 전면 정규화 + judge) — Claude normalize+judge

각 rep 의 전체 score.json 을 tier{n}/rep_{NN}.json 으로 저장(리줌: 있으면 건너뜀).
LLM 티어는 temperature=0.7 로 샘플링해 30개 분포를 만든다(통계 유의성 검정용).

실행: PYTHONIOENCODING=utf-8 PYTHONPATH=. <env>/python.exe scripts/run_30reps.py [tier1 tier2 tier3]
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# .env 의 ANTHROPIC_API_KEY 끝에 비ASCII 가 붙어있어도 메모리에서 정리(헤더 인코딩 에러 방지).
load_dotenv(PROJECT_ROOT / ".env")
_raw = os.environ.get("ANTHROPIC_API_KEY", "")
os.environ["ANTHROPIC_API_KEY"] = "".join(c for c in _raw if c.isascii()).strip()

from src.scoring.evaluate import (  # noqa: E402
    evaluate_golden,
    evaluate_golden_full,
    evaluate_golden_ontology_policy_judge,
)
from src.scoring.golden import load_golden_master  # noqa: E402
from src.scoring.scorer import score_cases  # noqa: E402

OUT = PROJECT_ROOT / "database" / "gemma4_30reps"
REPS = 30
WORKERS = 5
TEMP = 0.7
PAGES = dict(contract_pages=22, im_pages=32)

TIERS = {
    "tier1": {"mode": "ontology_policy", "needs_llm": False},
    "tier2": {"mode": "ontology_policy_judge", "needs_llm": True},
    "tier3": {"mode": "harness_norm_judge", "needs_llm": True},
}


def _client():
    from src.client.anthropic_client import AnthropicJSONClient

    return AnthropicJSONClient(temperature=TEMP)


def _evaluate(tier: str, cases):
    if tier == "tier1":
        return evaluate_golden(cases, mode="ontology_policy", **PAGES)
    if tier == "tier2":
        return evaluate_golden_ontology_policy_judge(cases, client=_client(), **PAGES)
    if tier == "tier3":
        return evaluate_golden_full(cases, client=_client(), **PAGES)
    raise ValueError(tier)


def _run_rep(tier: str, rep: int, cases) -> tuple[int, dict | None, str]:
    dest = OUT / tier / f"rep_{rep:02d}.json"
    if dest.exists():  # 리줌: 이미 완료
        rep_json = json.loads(dest.read_text(encoding="utf-8"))
        return rep, rep_json["metrics"], "skip"
    t0 = time.time()
    records = _evaluate(tier, cases)
    report = score_cases(
        records,
        mode=TIERS[tier]["mode"],
        golden_version="v0.2",
        run_id=f"30reps_{tier}_rep{rep:02d}",
    )
    report["temperature"] = 0.0 if tier == "tier1" else TEMP
    report["rep"] = rep
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return rep, report["metrics"], f"{time.time() - t0:.0f}s"


def run_tier(tier: str, cases) -> None:
    print(f"\n=== {tier} ({TIERS[tier]['mode']}) × {REPS} reps ===", flush=True)
    workers = WORKERS if TIERS[tier]["needs_llm"] else 1
    f2s = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_run_rep, tier, r, cases): r for r in range(1, REPS + 1)}
        for fut in as_completed(futs):
            try:
                rep, metrics, took = fut.result()
                f2s.append(metrics["f2"])
                print(
                    f"  {tier} rep{rep:02d} [{took}] "
                    f"F2={metrics['f2']:.4f} EI={metrics['efficiency_index_pct']:.2f} "
                    f"P={metrics['precision']:.3f} R={metrics['recall']:.3f}",
                    flush=True,
                )
            except Exception as exc:  # rep 단위 실패는 격리(재실행 시 보충)
                print(f"  {tier} rep{futs[fut]:02d} FAILED: {type(exc).__name__}: {exc}", flush=True)
    if f2s:
        import statistics

        print(
            f"  -> {tier} F2 mean={statistics.mean(f2s):.4f} "
            f"sd={statistics.pstdev(f2s):.4f} n={len(f2s)}",
            flush=True,
        )


def main() -> int:
    which = [a for a in sys.argv[1:] if a in TIERS] or list(TIERS)
    cases = load_golden_master()
    print(f"골든셋 {len(cases)}케이스 | 티어 {which} | reps={REPS} workers={WORKERS} temp={TEMP}", flush=True)
    for tier in which:
        run_tier(tier, cases)
    print("\nALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
