"""3조건 비교 리포트(compare.md) 렌더러 (docs/INTERFACES.md §7).

score.json dict 들을 입력받아 사람이 읽는 markdown 표를 만든다.
"""

from __future__ import annotations

from typing import Sequence

_MODE_LABEL = {
    "baseline": "① baseline",
    "ontology": "② +ontology",
    "guard": "③ +guard",
}
_MODE_ORDER = {"baseline": 0, "ontology": 1, "guard": 2}
_DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def _label(mode: str) -> str:
    return _MODE_LABEL.get(mode, mode)


def _sorted_reports(reports: Sequence[dict]) -> list[dict]:
    return sorted(reports, key=lambda r: _MODE_ORDER.get(r.get("mode", ""), 99))


def _difficulties(reports: Sequence[dict]) -> list[str]:
    seen: set[str] = set()
    for report in reports:
        seen.update(report.get("by_difficulty", {}).keys())
    ordered = [d for d in _DIFFICULTY_ORDER if d in seen]
    extras = sorted(seen - set(_DIFFICULTY_ORDER))
    return ordered + extras


def render_compare_md(
    reports: Sequence[dict], *, model: str = "?", seed: str = "?"
) -> str:
    """score.json dict 리스트 → compare.md 문자열."""
    if not reports:
        raise ValueError("render_compare_md needs at least one report")

    ordered = _sorted_reports(reports)
    first = ordered[0]
    n_cases = first.get("n_cases", "?")
    golden = first.get("golden_version", "?")

    lines: list[str] = []
    lines.append(
        f"# 3조건 비교 (n={n_cases}, golden={golden}, model={model}, seed={seed})\n"
    )

    # 핵심 지표
    lines.append("## 핵심 지표\n")
    lines.append("| 조건 | Accuracy | Precision | Recall ★ | F1 | 모르겠다 | 환각률 |")
    lines.append("|---|--:|--:|--:|--:|--:|--:|")
    for report in ordered:
        m = report["metrics"]
        review = report.get("review", {})
        review_count = review.get("count", 0)
        lines.append(
            f"| {_label(report['mode'])} "
            f"| {m['accuracy']:.3f} | {m['precision']:.3f} | {m['recall']:.3f} "
            f"| {m['f1']:.3f} | {review_count} | {m['hallucination_rate']:.3f} |"
        )
    lines.append("")

    # 통계 (Stage D 에서 채움)
    lines.append("## 통계 (Stage D)\n")
    lines.append("- McNemar p-value (③ vs ①): __")
    lines.append("- Bootstrap 95% CI on F1 (③): [__, __]\n")

    # 난이도별 Recall
    difficulties = _difficulties(ordered)
    if difficulties:
        header = "| 난이도 | " + " | ".join(_label(r["mode"]) for r in ordered) + " |"
        sep = "|---|" + "--:|" * len(ordered)
        lines.append("## 난이도별 Recall\n")
        lines.append(header)
        lines.append(sep)
        for diff in difficulties:
            cells = []
            for report in ordered:
                entry = report.get("by_difficulty", {}).get(diff)
                cells.append(f"{entry['recall']:.3f}" if entry else "—")
            lines.append(f"| {diff} | " + " | ".join(cells) + " |")
        lines.append("")

    return "\n".join(lines) + "\n"
