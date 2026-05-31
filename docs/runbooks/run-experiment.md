# Run Experiment Runbook

## 목적

같은 골든셋으로 3조건을 실행해 온톨로지와 가드가 불일치 탐지 성능을 개선하는지 비교한다.

## 조건

| 조건 | 설명 |
|---|---|
| baseline | LLM 단독 자유 질문 |
| ontology | 4개념 구조화 추출 + 교차검증 |
| guard | ontology 조건 + G1/G2/G3 가드 |

## 현재 상태

실험 runner와 CLI는 아직 구현되지 않았다. 구현 전에는 `docs/ROADMAP.md`, `docs/INTERFACES.md`, `docs/GOLDENSET.md`를 기준으로 입력/출력 형식을 맞춘다.

## 예상 명령

```bash
uv run dnb run --mode baseline
uv run dnb run --mode ontology
uv run dnb run --mode guard
uv run dnb compare reports/<baseline> reports/<ontology> reports/<guard>
```

## 재현성 규칙

- 같은 입력 PDF와 같은 골든셋을 사용한다.
- seed, model id, prompt version, timestamp를 `manifest.json`에 기록한다.
- 실행 결과는 `reports/<run_id>/`에 보존한다.
