# Local Setup Runbook

## 목적

로컬에서 테스트와 추출 스크립트를 실행할 수 있는 최소 환경을 맞춘다.

## 절차

```bash
uv sync --dev
```

`.env`에는 API 키를 둔다. `.env`는 커밋하지 않는다.

```bash
ANTHROPIC_API_KEY=...
```

기본 테스트를 실행한다.

```bash
uv run pytest
```

## 보안

- `database/*.pdf`는 외부 업로드하지 않는다.
- `.env`와 실행 산출물은 커밋하지 않는다.
