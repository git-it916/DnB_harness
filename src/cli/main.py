"""DnB Harness CLI — 추출(run) / 채점(score) / 비교(compare).

INTERFACES.md §1 인터페이스 지도의 진입점을 한 명령으로 묶는다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer

from src.scoring.compare import render_compare_md
from src.scoring.evaluate import SUPPORTED_MODES, evaluate_golden
from src.scoring.golden import DEFAULT_GOLDEN_PATH, load_golden_master
from src.scoring.scorer import score_cases
from src.stats.bootstrap import bootstrap_f1_ci
from src.stats.mcnemar import mcnemar_test
from src.stats.paired import aligned_correctness, mismatch_arrays

app = typer.Typer(
    help="DnB Harness — 온톨로지 기반 신탁계약서 검증 하네스 CLI",
    no_args_is_help=True,
    add_completion=False,
)

_FULL_PIPELINE_SCRIPT = "scripts/extract_full_pipeline.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@app.command()
def score(
    out: Path = typer.Option(..., "--out", "-o", help="score.json 출력 경로"),
    mode: str = typer.Option(
        "guard", "--mode", "-m", help=f"채점 모드 {SUPPORTED_MODES} (baseline 은 run 후 채점)"
    ),
    golden: Path = typer.Option(DEFAULT_GOLDEN_PATH, "--golden", "-g", help="골든 마스터 CSV"),
    contract_pages: int = typer.Option(22, help="신탁계약서 PDF 페이지 수 (G2 기준)"),
    im_pages: int = typer.Option(32, help="IM PDF 페이지 수 (G2 기준)"),
    run_id: str = typer.Option("adhoc", help="score.json 의 run_id"),
) -> None:
    """골든셋을 하네스 로직(결정적)에 통과시켜 score.json 산출."""
    try:
        cases = load_golden_master(golden)
        records = evaluate_golden(
            cases, mode=mode, contract_pages=contract_pages, im_pages=im_pages
        )
    except (ValueError, FileNotFoundError) as exc:
        typer.echo(f"[error] {exc}", err=True)
        raise typer.Exit(code=2)

    report = score_cases(records, mode=mode, golden_version="v0.1", run_id=run_id)
    _write_json(out, report)
    m = report["metrics"]
    review = report.get("review", {})
    typer.echo(
        f"[{mode}] P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
        f"모르겠다={review.get('count', 0)} 환각={m['hallucination_rate']:.3f}  ->  {out}"
    )


@app.command()
def compare(
    scores: list[Path] = typer.Argument(..., help="비교할 score.json 들 (2개 이상)"),
    out: Path = typer.Option(..., "--out", "-o", help="compare.md 출력 경로"),
    model: str = typer.Option("?", help="모델명 (리포트 헤더용)"),
    seed: str = typer.Option("?", help="시드 (리포트 헤더용)"),
) -> None:
    """여러 score.json 을 3조건 비교 markdown 으로 합친다."""
    try:
        reports = [json.loads(p.read_text(encoding="utf-8")) for p in scores]
        markdown = render_compare_md(reports, model=model, seed=seed)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        typer.echo(f"[error] {exc}", err=True)
        raise typer.Exit(code=2)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    typer.echo(f"compare ({len(reports)}개 조건)  ->  {out}")


@app.command()
def stats(
    score_a: Path = typer.Argument(..., help="기준 조건 score.json (예: baseline 또는 ontology)"),
    score_b: Path = typer.Argument(..., help="비교 조건 score.json (예: guard)"),
    out: Path = typer.Option(None, "--out", "-o", help="통계 결과 JSON 출력 경로(선택)"),
    n_boot: int = typer.Option(2000, help="부트스트랩 반복 수"),
    seed: int = typer.Option(42, help="부트스트랩 시드"),
) -> None:
    """McNemar(A vs B) + B 조건 F1 부트스트랩 95% CI."""
    try:
        report_a = json.loads(score_a.read_text(encoding="utf-8"))
        report_b = json.loads(score_b.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        typer.echo(f"[error] {exc}", err=True)
        raise typer.Exit(code=2)

    try:
        correct_a, correct_b = aligned_correctness(report_a, report_b)
        mc = mcnemar_test(correct_a, correct_b)
        gold_b, pred_b = mismatch_arrays(report_b)
        f1_ci = bootstrap_f1_ci(gold_b, pred_b, n_boot=n_boot, seed=seed)
    except ValueError as exc:
        typer.echo(f"[error] {exc}", err=True)
        raise typer.Exit(code=2)

    mode_a, mode_b = report_a.get("mode", "A"), report_b.get("mode", "B")
    typer.echo(
        f"McNemar ({mode_a} vs {mode_b}): b={mc.b} c={mc.c} "
        f"p={mc.p_value:.4f} [{mc.method}]"
    )
    typer.echo(
        f"Bootstrap F1 ({mode_b}): {f1_ci.point:.3f} "
        f"95% CI [{f1_ci.lo:.3f}, {f1_ci.hi:.3f}] (n_boot={f1_ci.n_boot})"
    )

    if out is not None:
        payload = {
            "mcnemar": {
                "mode_a": mode_a, "mode_b": mode_b,
                "b": mc.b, "c": mc.c, "n_discordant": mc.n_discordant,
                "statistic": mc.statistic, "p_value": mc.p_value, "method": mc.method,
            },
            "bootstrap_f1": {
                "mode": mode_b, "point": f1_ci.point, "lo": f1_ci.lo, "hi": f1_ci.hi,
                "n_boot": f1_ci.n_boot, "ci": f1_ci.ci,
            },
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        typer.echo(f"stats  ->  {out}")


@app.command()
def run(
    seeds: str = typer.Option("42", help="콤마 구분 시드 (예: 42,1,2)"),
    model: str = typer.Option("gemma4:31b", help="Ollama 모델"),
    with_normalize: bool = typer.Option(False, "--with-normalize", help="Claude 정규화"),
    with_judge: bool = typer.Option(False, "--with-judge", help="Claude LLM Judge"),
) -> None:
    """전체 파이프라인 실행 (Ollama 추출 → 가드 → 온톨로지/SHACL → cross_check)."""
    cmd = [sys.executable, _FULL_PIPELINE_SCRIPT, "--seeds", seeds, "--model", model]
    if with_normalize:
        cmd.append("--with-normalize")
    if with_judge:
        cmd.append("--with-judge")
    typer.echo(f"$ {' '.join(cmd)}")
    raise typer.Exit(code=subprocess.call(cmd))


if __name__ == "__main__":
    app()
