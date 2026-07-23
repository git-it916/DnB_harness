# Local Review Web Runbook

## 목적

신탁계약서와 투자제안서(IM)를 로컬 웹에서 업로드하고, 온톨로지 정책 기반 판정과
사용자 확인이 필요한 항목을 한 화면에서 검토한다.

## 최초 설정

```bash
uv sync --dev
cd web
pnpm install
pnpm build
cd ..
```

웹 검토는 기존 하네스와 동일하게 Anthropic API로 두 PDF의 14개 필드를 추출하고,
`ontology_policy_judge`에서 필요한 경우 같은 Anthropic provider로 선택적 Judge를
호출한다. `.env`에 `ANTHROPIC_API_KEY`가 필요하다.

웹 API와 실행 기록은 로컬에서 관리하지만, 업로드한 PDF 원문은 추출·판정을 위해
Anthropic API로 전송된다. 실제 계약 문서를 사용할 때는 조직의 외부 전송 정책을 먼저
확인한다.

기본 모델은 `claude-sonnet-4-6`이며, 다른 모델은 `ANTHROPIC_MODEL`로 지정할 수 있다.
웹 경로에는 Ollama가 필요하지 않다.

## 실행

```bash
uv run python -m src.web_api
```

기본 주소는 `http://127.0.0.1:8000`이다. 포트가 사용 중이면 다음처럼 바꾼다.

```bash
DNB_PORT=8010 uv run python -m src.web_api
```

브라우저에서 `http://127.0.0.1:8010`을 연다.

## 개발 모드

터미널 1:

```bash
uv run uvicorn src.web_api.app:app --host 127.0.0.1 --port 8000
```

터미널 2:

```bash
cd web
pnpm dev
```

Vite 개발 주소는 `http://127.0.0.1:5173`이며 `/api` 요청을 8000 포트로 전달한다.

## 사용자 판정

`needs_human_review` 항목에서는 다음 중 하나를 선택한다.

- `같음`: 현재 실행을 `match`로 확정한다.
- `다름`: 현재 실행을 `mismatch`로 확정한다.
- `판단 보류`: 보류 상태를 유지한다.

Judge가 `same` 또는 `different`로 확정한 필드는 사용자 확인 없이 자동 처리된다.
사용자 확인은 Judge가 결론을 내리지 못했거나, 호출 실패·근거 부족으로 안전하게
확정할 수 없는 항목에만 표시된다.

펀드명·운용사·신탁업자·판매사에서 `같음`을 선택한 경우에만 “앞으로도 같은 명칭으로
사용”을 선택할 수 있다. 이 선택은 로컬 SQLite의 Alias Registry에 기록되며 연구용
골든셋에는 영향을 주지 않는다.

## 로컬 데이터

기본 저장 위치:

```text
var/
  dnb.sqlite3
  runs/<run_id>/
    input/contract.pdf
    input/im.pdf
    review_result.json
    abox.ttl
    shacl_report.txt
```

다른 위치를 사용하려면 `DNB_LOCAL_ROOT` 환경변수를 설정한다. `var/`와 PDF 원문은
커밋하거나 외부 서비스에 업로드하지 않는다.

## 확인 명령

```bash
curl http://127.0.0.1:8000/api/v1/health
uv run pytest
cd web && pnpm build
```
