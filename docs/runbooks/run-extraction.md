# Run Extraction Runbook

## 목적

현재 추출 PoC를 실행해 신탁계약서와 IM에서 구조화 결과를 만든다.

## Claude 경로

```bash
uv run python scripts/run_extract_once.py
```

주요 코드:

- `src/pipelines/extract.py`
- `src/client/anthropic_client.py`
- `src/schemas/extraction.py`
- `prompts/v0/extract/system.md`

## Gemma 경로

Gemma/Ollama 경로의 상세 설계와 검증 기록은 `docs/reference/extract_guard_plan.md`에 둔다.

```bash
uv run python scripts/hello_gemma.py
```

## 산출물

실행 결과는 `reports/` 아래에 생성한다. 자동 생성 산출물은 기본적으로 커밋하지 않는다.
