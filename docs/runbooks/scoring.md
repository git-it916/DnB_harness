# Scoring Runbook

## 목적

하네스 판정 결과를 `tests/golden/golden_master.csv`와 비교해 점수(`score.json`)를 산출한다.

## 현재 상태

`src/scoring/` 구현 완료. 실제 실행 절차와 실측 결과는 [`reproduce-results.md §1`](./reproduce-results.md)에 있다.

## 구현 기준 (지켜진 계약)

- 채점기는 LLM을 호출하지 않는 순수 함수다 (`score_cases`).
- `gold_label=mismatch`를 positive로 본다.
- `gold_label=missing`은 confusion 분모·분자에서 제외한다 (재현율 페널티 없음).
- 가드가 reject한 필드는 `final_status`가 missing_evidence여도 예측을 mismatch로 본다 (재현율 우선, `GOLDENSET §7`).
- `final_status=needs_review`는 mismatch 확정이 아니라 `predicted_label=review`로 분리한다. `score.json`은 전체 중 모르겠다 개수/비율을 `review.count`와 `review.rate`로 기록한다.
- 필드·난이도·변조유형·harness signal별 breakdown은 별도 함수로 분리한다.
- `FinalCheckStatus → predicted_label` 매핑은 `docs/GOLDENSET.md §7`(`FINAL_TO_PREDICTED`)이 단일 진실 소스.

## 모듈

| 파일 | 역할 |
|---|---|
| `src/scoring/golden.py` | `golden_master.csv` 로더 (utf-8-sig) |
| `src/scoring/labels.py` | `FINAL_TO_PREDICTED`, `predicted_label()` |
| `src/scoring/scorer.py` | `CaseRecord`, `score_cases()` → score.json |
| `src/scoring/breakdown.py` | by_field/difficulty/mutation/signal |
| `src/scoring/evaluate.py` | 결정적 평가기 (골든 → 하네스 로직, LLM 불필요) |
| `src/scoring/compare.py` | 3조건 compare.md 렌더러 |
| `tests/test_scoring.py` | 채점 단위 테스트 |

## 명령

```bash
python -m src.cli score --mode guard --out reports/scoring/score_guard.json
```

전체 절차(ontology/guard, compare, stats, 라이브)는 [`reproduce-results.md`](./reproduce-results.md) 참조.
