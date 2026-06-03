# Run Experiment Runbook

## 목적

같은 골든셋으로 3조건을 실행해 온톨로지와 가드가 불일치 탐지 성능을 개선하는지 비교한다.

## 조건

| 조건 | 설명 |
|---|---|
| baseline | LLM 단독 자유 질문 |
| ontology | 4개념 구조화 추출 + ABox/SHACL 진단 + 교차검증. SHACL 위반은 기록만 하고 결과 수정 없음 |
| guard | ontology 조건 + G1/G2/G3 가드. G3가 Python 규칙/SHACL 신호를 reject/null 처리로 집행 |

## 현재 상태

CLI(`src/cli`)·하네스 러너(`src/harness`)·채점(`src/scoring`)·통계(`src/stats`) 구현 완료. 실제 실행·실측 결과는 [`reproduce-results.md`](./reproduce-results.md)에 있다. 남은 것은 골든셋 freeze 와 baseline 라이브 채점.

## 명령

> conda env `dnb_harness` 사용. `uv run` 금지. (Windows: `set PYTHONIOENCODING=utf-8`)

```bash
# 단일 모드 라이브 풀런 (Ollama 필요)
python scripts/harness_run.py --mode guard --seed 42

# 결정적 채점 + 비교 + 통계 (LLM 불필요)
python -m src.cli score   --mode ontology --out reports/scoring/score_ontology.json
python -m src.cli score   --mode guard    --out reports/scoring/score_guard.json
python -m src.cli compare reports/scoring/score_ontology.json reports/scoring/score_guard.json --out reports/compare.md
python -m src.cli stats   reports/scoring/score_ontology.json reports/scoring/score_guard.json --out reports/stats.json
```

단계별 실측 출력은 [`reproduce-results.md`](./reproduce-results.md) 참조.

## 재현성 규칙

- 같은 입력 PDF와 같은 골든셋을 사용한다.
- seed, model id, prompt version, timestamp를 `manifest.json`에 기록한다.
- 실행 결과는 `reports/<run_id>/`에 보존한다.
