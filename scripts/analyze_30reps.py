"""gemma4_30reps 3-tier 분포 통계 + 유의성 검정 → stats.json.

- 티어별 F2/EI/Precision/Recall 분포(평균·표준편차·95% CI·min/max).
- 유의성:
    tier3 vs tier2 : Welch 2표본 t검정 + Mann-Whitney U + Cohen's d
    tier2 vs tier1, tier3 vs tier1 : tier1 은 상수(결정적) → 1표본 t검정(popmean=tier1)
- 분산이 0이면(LLM 흔들림 없음) 검정 불가로 표시하고 원시 차이를 보고.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(__file__).resolve().parent.parent / "database" / "gemma4_30reps"
TIERS = ["tier1", "tier2", "tier3"]
TIER_MODE = {
    "tier1": "ontology_policy (LLM 없음·결정적)",
    "tier2": "ontology_policy_judge (결정적+선택 judge)",
    "tier3": "harness_norm_judge (LLM 전면 정규화+judge)",
}
METRICS = ["f2", "efficiency_index_pct", "precision", "recall", "f1", "accuracy"]


def _collect(tier: str) -> dict[str, list[float]]:
    reps = sorted((OUT / tier).glob("rep_*.json"))
    data: dict[str, list[float]] = {m: [] for m in METRICS}
    conf: dict[str, list[int]] = {k: [] for k in ("tp", "fp", "fn", "tn")}
    for p in reps:
        d = json.loads(p.read_text(encoding="utf-8"))
        for m in METRICS:
            data[m].append(float(d["metrics"][m]))
        for k in conf:
            conf[k].append(int(d["confusion"][k]))
    data["_conf"] = conf  # type: ignore
    data["_n"] = len(reps)  # type: ignore
    return data


def _desc(x: list[float]) -> dict:
    a = np.asarray(x, dtype=float)
    n = len(a)
    sd = float(np.std(a, ddof=1)) if n > 1 else 0.0
    mean = float(np.mean(a)) if n else 0.0
    if n > 1 and sd > 0:
        ci = stats.t.interval(0.95, n - 1, loc=mean, scale=sd / math.sqrt(n))
        ci = [float(ci[0]), float(ci[1])]
    else:
        ci = [mean, mean]
    return {
        "n": n,
        "mean": round(mean, 4),
        "sd": round(sd, 4),
        "min": round(float(np.min(a)), 4) if n else 0.0,
        "max": round(float(np.max(a)), 4) if n else 0.0,
        "median": round(float(np.median(a)), 4) if n else 0.0,
        "ci95": [round(ci[0], 4), round(ci[1], 4)],
    }


def _cohens_d(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    s = math.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2) if len(a) > 1 and len(b) > 1 else 0.0
    return round(float((np.mean(a) - np.mean(b)) / s), 4) if s > 0 else float("nan")


def _two_sample(a: list[float], b: list[float], name_a: str, name_b: str) -> dict:
    aa, bb = np.asarray(a, float), np.asarray(b, float)
    va, vb = (np.var(aa, ddof=1) if len(aa) > 1 else 0.0), (np.var(bb, ddof=1) if len(bb) > 1 else 0.0)
    res = {
        "comparison": f"{name_a} vs {name_b}",
        "mean_diff": round(float(np.mean(aa) - np.mean(bb)), 4),
        "cohens_d": _cohens_d(aa, bb),
    }
    if va == 0 and vb == 0:
        res.update(test="degenerate(분산 0)", note="두 표본 모두 변동 없음 → t검정 불가. 원시 차이로 판단.",
                   t_stat=None, p_value=None)
        return res
    t = stats.ttest_ind(aa, bb, equal_var=False)  # Welch
    u = stats.mannwhitneyu(aa, bb, alternative="two-sided") if (va > 0 or vb > 0) else None
    res.update(
        test="welch_t",
        t_stat=round(float(t.statistic), 4),
        p_value=float(t.pvalue),
        significant_p05=bool(t.pvalue < 0.05),
        mannwhitney_p=(float(u.pvalue) if u is not None else None),
    )
    return res


def _one_sample_vs_const(a: list[float], const: float, name_a: str, name_b: str) -> dict:
    aa = np.asarray(a, float)
    res = {"comparison": f"{name_a} vs {name_b}(상수={round(const,4)})",
           "mean_diff": round(float(np.mean(aa) - const), 4)}
    if len(aa) < 2 or np.var(aa, ddof=1) == 0:
        res.update(test="degenerate(표본 분산 0)", t_stat=None, p_value=None,
                   note="표본 변동 없음 → 1표본 t검정 불가. 원시 차이로 판단.")
        return res
    t = stats.ttest_1samp(aa, popmean=const)
    res.update(test="one_sample_t", t_stat=round(float(t.statistic), 4),
               p_value=float(t.pvalue), significant_p05=bool(t.pvalue < 0.05))
    return res


def main() -> int:
    tiers = {t: _collect(t) for t in TIERS}
    summary = {}
    for t in TIERS:
        summary[t] = {
            "mode": TIER_MODE[t],
            "n_reps": tiers[t]["_n"],
            "metrics": {m: _desc(tiers[t][m]) for m in METRICS},
            "confusion_mean": {k: round(float(np.mean(v)), 2) for k, v in tiers[t]["_conf"].items()},
        }

    f2 = {t: tiers[t]["f2"] for t in TIERS}
    ei = {t: tiers[t]["efficiency_index_pct"] for t in TIERS}
    t1_f2 = float(np.mean(f2["tier1"])) if f2["tier1"] else 0.0
    t1_ei = float(np.mean(ei["tier1"])) if ei["tier1"] else 0.0

    tests = {
        "F2": {
            "tier3_vs_tier2": _two_sample(f2["tier3"], f2["tier2"], "tier3", "tier2"),
            "tier2_vs_tier1": _one_sample_vs_const(f2["tier2"], t1_f2, "tier2", "tier1"),
            "tier3_vs_tier1": _one_sample_vs_const(f2["tier3"], t1_f2, "tier3", "tier1"),
        },
        "EI": {
            "tier3_vs_tier2": _two_sample(ei["tier3"], ei["tier2"], "tier3", "tier2"),
            "tier2_vs_tier1": _one_sample_vs_const(ei["tier2"], t1_ei, "tier2", "tier1"),
            "tier3_vs_tier1": _one_sample_vs_const(ei["tier3"], t1_ei, "tier3", "tier1"),
        },
    }

    out = {"reps": {t: tiers[t]["_n"] for t in TIERS}, "summary": summary, "significance": tests,
           "raw_f2": f2, "raw_ei": ei}
    (OUT / "stats.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # 콘솔 요약
    print("=== 티어별 F2 / EI 분포 ===")
    for t in TIERS:
        s = summary[t]["metrics"]
        print(f"{t}: F2 {s['f2']['mean']}±{s['f2']['sd']} (CI {s['f2']['ci95']}) | "
              f"EI {s['efficiency_index_pct']['mean']}±{s['efficiency_index_pct']['sd']} | "
              f"R {s['recall']['mean']}±{s['recall']['sd']} | n={summary[t]['n_reps']}")
    print("\n=== 유의성 (F2) ===")
    for k, v in tests["F2"].items():
        print(f"{k}: {v}")
    print("\n저장:", OUT / "stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
