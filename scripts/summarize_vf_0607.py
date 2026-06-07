"""gemma4_vf_0607 3조건 score JSON → 비교 요약(summary.md).

메인 지표 F2-Score, 실무 정량화 지표 EI(업무 효율성 점수)를 표로 정리한다.
EI(%) = (1 - (T_AI + FP*T_REVIEW)/T_MANUAL)*100  (180/2.5/2.0분).
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path("database/gemma4_vf_0607")

# (표시명, 파일 mode, 설명)
CONDITIONS = [
    ("① harness_norm_judge", "harness_norm_judge", "가드+정규화(LLM)+judge(LLM) — LLM 중심"),
    ("② ontology_policy", "ontology_policy", "기본 룰 가드(결정적 캐노니컬, judge 없음)"),
    ("③ ontology_policy_judge", "ontology_policy_judge", "캐노니컬 + 필드전용 judge fallback"),
]


def _load(mode: str) -> dict | None:
    p = OUT / f"score_{mode}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    rows = []
    for name, mode, desc in CONDITIONS:
        rep = _load(mode)
        if rep is None:
            rows.append((name, mode, desc, None))
            continue
        rows.append((name, mode, desc, rep))

    lines: list[str] = []
    lines.append("# gemma4_vf_0607 — 3조건 성능 비교 (골든셋 v0.2, 80케이스)\n")
    lines.append("> 메인 지표 **F2-Score**(재현율 2배 가중) · 실무 지표 **EI**(업무 효율성 점수).\n")
    lines.append("> EI(%) = (1 − (T_AI + FP×T_Review) / T_Manual) × 100,  "
                 "T_Manual=180분 · T_AI=2.5분 · T_Review=2분/건. 헛알람=FP.\n")

    lines.append("## 종합 비교\n")
    lines.append("| 조건 | TP | FP | FN | TN | review | Precision | Recall | F1 | **F2** | **EI(%)** |")
    lines.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for name, mode, desc, rep in rows:
        if rep is None:
            lines.append(f"| {name} | — | — | — | — | — | — | — | — | — | (미실행) |")
            continue
        m, c = rep["metrics"], rep["confusion"]
        rev = c.get("review", rep.get("review", {}).get("count", 0))
        lines.append(
            f"| {name} | {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} | {rev} | "
            f"{m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | "
            f"**{m['f2']:.3f}** | **{m['efficiency_index_pct']:.2f}** |"
        )

    lines.append("\n## 조건 설명\n")
    for name, mode, desc, rep in rows:
        lines.append(f"- **{name}** (`{mode}`): {desc}")

    lines.append("\n## EI 분해 (실무 재검토 시간)\n")
    lines.append("| 조건 | 헛알람(FP) | AI+재검토(분) | EI(%) |")
    lines.append("|---|--:|--:|--:|")
    for name, mode, desc, rep in rows:
        if rep is None:
            lines.append(f"| {name} | — | — | (미실행) |")
            continue
        e = rep["efficiency"]
        lines.append(f"| {name} | {e['false_alarms']} | {e['ai_plus_review_min']:.1f} | "
                     f"{e['index_pct']:.2f} |")

    md = "\n".join(lines) + "\n"
    (OUT / "summary.md").write_text(md, encoding="utf-8")
    print(md)
    print("저장:", OUT / "summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
