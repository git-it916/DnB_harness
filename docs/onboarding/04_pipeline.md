# ⚙️ 한승연 — Pipeline · CLI · End-to-End

> 너는 우리 시스템을 **"한 줄 명령으로 굴러가게"** 만드는 책임자.
> 각 모듈(승훈 scorer, 종현 LLM, 조건 가드)이 따로 동작해도 묶어주는 사람이 없으면 학술제 데모에서 죽는다.
> 풀스택 관심에 정확히 맞는 트랙.

---

## 1. 5분 컨셉

### CLI (Command Line Interface)
"한 줄로 시스템 전체를 돌릴 수 있게" 만드는 인터페이스.
우리 목표: `python -m src.cli run --fund igis_blackon_1 --model sonnet-4-6` 하면 PDF 로드 → LLM 호출 → 가드 → 채점 → 리포트까지 다 됨.

### `typer` 라이브러리
파이썬에서 CLI를 만드는 가장 간단한 방법. 함수 시그니처만 적어도 자동으로 `--옵션`이 생긴다.

### End-to-End Pipeline
"데이터 들어오는 시점부터 결과 리포트 나올 때까지의 전 과정". 우리 경우:
```
PDF → 로드 → 프롬프트 조립 → LLM 호출 → JSON 파싱
    → 가드 통과 → 골든셋 채점 → 메트릭 집계 → 리포트 생성
```
각 단계는 다른 사람이 만들지만, **이걸 한 줄로 묶는 게 네 일**.

### Run ID & Reports
모든 실행은 고유 `run_id` 를 받고, 결과는 `reports/<run_id>/` 아래 저장.
→ "어제 실험과 오늘 실험이 뭐가 다른가" 추적 가능.

### Idempotent / 멱등성
같은 입력으로 두 번 실행해도 결과가 같아야 함 (LLM 출력 제외). 캐시·시드 관리.

---

## 2. 0주차 체크리스트

- [ ] [공통 README](./README.md) 0주차 셋업 완료
- [ ] `typer` 라이브러리 첫 만남 — Hello World 한 번:
  ```python
  # scripts/hello_typer.py
  import typer
  app = typer.Typer()

  @app.command()
  def hello(name: str = "world"):
      print(f"Hello, {name}!")

  if __name__ == "__main__":
      app()
  ```
  ```bash
  python scripts/hello_typer.py hello --name 승연
  ```

---

## 3. 1주차: CLI 골격 + smoke 명령

### 목표
`python -m src.cli smoke --fund igis_blackon_1` 으로 **PDF 1개 로드 → Claude 1번 호출 → JSON 받아서 콘솔 출력** 까지의 최소 동작.

### 산출물 1: `src/cli.py`

```python
# src/cli.py
import uuid
from datetime import datetime
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="DnB Harness CLI")
console = Console()

def new_run_id() -> str:
    """타임스탬프 + 짧은 uuid → 'run_20260524_153012_a1b2'"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"run_{ts}_{uuid.uuid4().hex[:4]}"

@app.command()
def smoke(
    fund: str = typer.Option(..., help="펀드 ID, 예: igis_blackon_1"),
    model: str = typer.Option("claude-haiku-4-5-20251001", help="테스트는 Haiku로"),
):
    """최소 동작 확인: PDF 1개 로드 → Claude 호출 → 응답 출력."""
    run_id = new_run_id()
    console.rule(f"[bold cyan]Smoke Test — {run_id}")
    pdf_dir = Path(f"database/{fund}")
    pdfs = list(pdf_dir.glob("*.pdf"))
    if not pdfs:
        console.print(f"[red]PDF 없음: {pdf_dir}")
        raise typer.Exit(1)

    console.print(f"발견된 PDF: {len(pdfs)}개")
    for p in pdfs:
        console.print(f"  - {p.name} ({p.stat().st_size // 1024} KB)")

    # 종현이 만든 호출 코드 사용
    from src.client.anthropic_client import HarnessClient
    client = HarnessClient(model=model)
    result = client.call_with_pdfs(
        system_prompt="당신은 사모펀드 DD 전문가입니다.",
        pdfs=pdfs[:1],  # smoke니까 1개만
        user_message="이 펀드의 정식 명칭만 한 줄로 답해주세요.",
    )

    # rich 테이블로 결과 출력
    t = Table(title="응답")
    t.add_column("필드"); t.add_column("값")
    for k, v in result["usage"].items():
        t.add_row(k, str(v))
    console.print(t)

    # 텍스트 응답 보기
    for block in result["response"].content:
        if hasattr(block, "text"):
            console.print(f"[green]답: {block.text}")

@app.command()
def run(
    fund: str = typer.Option(...),
    model: str = typer.Option("claude-sonnet-4-6"),
    suite: str = typer.Option("all", help="all|extract|consistency|risk"),
):
    """전체 eval 파이프라인 (2주차 산출물)."""
    console.print("[yellow]아직 구현 안 됨 — 2주차 작업")

if __name__ == "__main__":
    app()
```

```bash
# 동작 확인
python -m src.cli smoke --fund igis_blackon_1
```

### 산출물 2: `src/__init__.py`, `src/cli.py` 패키지 구조 정리

```
src/
├── __init__.py
├── cli.py
├── client/__init__.py
├── schemas/__init__.py
├── eval/__init__.py
├── guards/__init__.py
└── pipelines/__init__.py
```

각 빈 `__init__.py` 도 만들어 둬야 import 됨.

### DoD
- `python -m src.cli --help` 가 명령어 목록 보여줌
- `python -m src.cli smoke --fund igis_blackon_1` 실행 → 응답 출력 + 토큰 수 표
- README에 "CLI 사용법" 섹션 추가

---

## 4. 2주차: 전체 파이프라인 + 리포트 자동 생성

### 산출물 1: `run` 명령 풀 구현

```python
@app.command()
def run(
    fund: str = typer.Option(...),
    model: str = typer.Option("claude-sonnet-4-6"),
    guards_off: list[str] = typer.Option([], help="끌 가드 이름 목록 (ablation용)"),
):
    """전체 eval 파이프라인."""
    run_id = new_run_id()
    out_dir = Path(f"reports/{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. PDF 로드
    pdfs = list(Path(f"database/{fund}").glob("*.pdf"))

    # 2. LLM 호출 (종현 코드)
    from src.pipelines.extract_anchors_v0 import run_extract
    requested = load_requested_fields(fund)  # GT에 정의된 필드 목록
    extraction = run_extract(fund, requested)

    # 3. 가드 적용 (조건 코드)
    from src.guards.registry import ALL_GUARDS, run_guards
    enabled = set(ALL_GUARDS) - set(guards_off)
    guard_results = run_guards(
        [a.model_dump() for a in extraction.anchors],
        enabled=enabled,
        # ... 가드별 의존성
    )

    # 4. 채점 (승훈 코드)
    from src.eval.anchor_scorer import score_anchors
    gt = load_anchors_yaml(fund)
    kept = filter_rejected(extraction.anchors, guard_results)
    matches, em = score_anchors(gt, {a.field: a.value for a in kept})

    # 5. 리포트 생성
    write_report(out_dir, run_id, fund, model, em, matches, guard_results)
    console.print(f"[green]리포트 저장: {out_dir}/report.md")
```

### 산출물 2: 리포트 템플릿 + 자동 생성

```python
# src/pipelines/reporter.py
from pathlib import Path
import pandas as pd

REPORT_TEMPLATE = """# Eval Report — {run_id}

- **Fund**: `{fund}`
- **Model**: `{model}`
- **Prompt version**: `{prompt_version}`
- **Schema version**: `{schema_version}`
- **Date**: {date}

## 1. 종합 메트릭

| 메트릭 | 값 |
|--------|-----|
| Exact Match (EM) | {em:.3f} |
| Schema-valid rate | {schema_valid:.3f} |
| Cache hit rate | {cache_hit:.3f} |
| Cost (USD) | ${cost:.4f} |
| Latency p50 (s) | {p50:.1f} |

## 2. 항목별 결과

{anchor_table}

## 3. 가드 결과

{guard_table}

## 4. 비용·토큰 상세

{usage_table}
"""

def write_report(out_dir: Path, run_id: str, fund: str, model: str,
                 em: float, matches, guard_results) -> None:
    # pandas로 표 markdown 변환
    df = pd.DataFrame([m.__dict__ for m in matches])
    anchor_table = df.to_markdown(index=False)

    g_df = pd.DataFrame([{
        "guard": g.guard_name,
        "passed": g.passed,
        "rejected": len(g.rejected_items),
    } for g in guard_results])
    guard_table = g_df.to_markdown(index=False)

    content = REPORT_TEMPLATE.format(
        run_id=run_id, fund=fund, model=model,
        prompt_version="v0", schema_version="v0.1",
        date="2026-05-30",
        em=em, schema_valid=1.0, cache_hit=0.0,
        cost=0.0, p50=0.0,
        anchor_table=anchor_table,
        guard_table=guard_table,
        usage_table="(TBD)",
    )
    (out_dir / "report.md").write_text(content, encoding="utf-8")
```

### 산출물 3: `reports/.gitkeep` + `.gitignore`

```gitignore
# .gitignore
database/*.pdf
database/**/*.pdf
.env
reports/*/
!reports/.gitkeep
__pycache__/
.pytest_cache/
*.pyc
```

### DoD
- `python -m src.cli run --fund igis_blackon_1` → `reports/run_xxx/report.md` 자동 생성
- 리포트에 메트릭 표 + 가드 표 + 항목별 결과 표 포함
- `python -m src.cli run --guards-off G2_citation` 같은 ablation 옵션 동작 (조건이 쓴다)

---

## 5. 막히면

| 증상 | 해결 |
|------|------|
| `python -m src.cli` 안 됨 (`No module named src`) | 루트 디렉토리에서 실행하고 있는지 확인. `src/__init__.py` 존재 확인. |
| `typer` 옵션이 한국어로 깨짐 | `chcp 65001` (UTF-8 모드) + 터미널 폰트 한국어 지원 |
| `pandas.to_markdown` 오류 | `pip install tabulate` 필요 |
| 모듈 import 순환 | 가드/스키마/scorer를 서로 import 안 하도록 분리. 데이터 클래스만 공유. |
| 리포트 파일이 한국어 깨짐 | `Path.write_text(..., encoding="utf-8")` 강제 |

---

## 6. 다음에 참고할 것

- Typer 공식: <https://typer.tiangolo.com/>
- Rich (테이블·진행바·로그): <https://rich.readthedocs.io/>
- Markdown 표 생성: `pandas.DataFrame.to_markdown()`
- Click vs Typer 비교 — typer가 type hint 기반이라 입문에 편함
- (옵션) Streamlit으로 리포트 웹 뷰어 만들기 — Phase 4 데모용
