# Scoring Runbook

## 목적

하네스 판정 결과를 `tests/golden/golden_master.csv`와 비교해 점수를 산출한다.

## 현재 상태

`src/scoring/`은 아직 구현되지 않았다. 다음 구현자는 `docs/GOLDENSET.md`와 `docs/INTERFACES.md`의 `score.json` 스키마를 먼저 확인한다.

## 구현 기준

- 채점기는 LLM을 호출하지 않는 순수 함수로 둔다.
- `gold_label=mismatch`를 positive로 본다.
- `gold_label=missing`은 mismatch 재현율/정밀도 계산의 분모에서 제외한다.
- 필드, 난이도, 변조 유형, harness signal별 breakdown을 별도 함수로 분리한다.

## 예상 산출물

- `src/scoring/scorer.py`
- `src/scoring/breakdown.py`
- `src/scoring/compare.py`
- `tests/test_scorer.py`
- `tests/test_breakdown.py`
- `tests/test_compare.py`
