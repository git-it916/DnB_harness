"""Stage B CLI + compare 렌더러 테스트 (TDD)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.cli.main import app
from src.scoring.compare import render_compare_md

runner = CliRunner()


# ── compare 렌더러 ───────────────────────────────────────────────────────────

def _fake_report(mode: str, recall: float) -> dict:
    return {
        "schema_version": "v0",
        "run_id": f"r_{mode}",
        "mode": mode,
        "golden_version": "v0.1",
        "n_cases": 30,
        "metrics": {
            "accuracy": 0.5,
            "precision": 0.6,
            "recall": recall,
            "f1": 0.55,
            "hallucination_rate": 0.0,
        },
        "confusion": {"tp": 1, "fp": 1, "fn": 1, "tn": 1, "missing_excluded": 4},
        "by_field": {},
        "by_difficulty": {
            "easy": {"n": 5, "accuracy": 1.0, "recall": 1.0},
            "hard": {"n": 13, "accuracy": 0.3, "recall": recall},
        },
        "by_mutation": {},
        "by_signal": {},
        "cases": [],
    }


def test_render_compare_md_has_metric_rows_per_mode():
    md = render_compare_md(
        [_fake_report("ontology", 0.6), _fake_report("guard", 0.9)],
        model="gemma4:31b",
    )
    assert "# 3조건 비교" in md
    assert "gemma4:31b" in md
    assert "+ontology" in md and "+guard" in md
    # recall 값이 표에 들어감
    assert "0.900" in md
    # 난이도별 표
    assert "난이도" in md and "hard" in md


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("score", "compare", "run"):
        assert cmd in result.stdout


def test_cli_score_writes_score_json(tmp_path: Path):
    out = tmp_path / "score_ontology.json"
    result = runner.invoke(
        app,
        ["score", "--mode", "ontology", "--out", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["mode"] == "ontology"
    assert report["n_cases"] == 30
    assert report["metrics"]["recall"] == 1.0  # 결정적: 변조 전부 탐지


def test_cli_score_rejects_unsupported_mode(tmp_path: Path):
    result = runner.invoke(
        app,
        ["score", "--mode", "baseline", "--out", str(tmp_path / "x.json")],
    )
    assert result.exit_code != 0


def test_cli_compare_writes_markdown(tmp_path: Path):
    s1 = tmp_path / "a.json"
    s2 = tmp_path / "b.json"
    s1.write_text(json.dumps(_fake_report("ontology", 0.6)), encoding="utf-8")
    s2.write_text(json.dumps(_fake_report("guard", 0.9)), encoding="utf-8")
    out = tmp_path / "compare.md"
    result = runner.invoke(app, ["compare", str(s1), str(s2), "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert "3조건 비교" in out.read_text(encoding="utf-8")
