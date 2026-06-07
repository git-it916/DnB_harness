# gemma4_vf_0607 — 3조건 성능 비교 (골든셋 v0.2, 80케이스)

> 메인 지표 **F2-Score**(재현율 2배 가중) · 실무 지표 **EI**(업무 효율성 점수).

> EI(%) = (1 − (T_AI + FP×T_Review) / T_Manual) × 100,  T_Manual=180분 · T_AI=2.5분 · T_Review=2분/건. 헛알람=FP.

## 종합 비교

| 조건 | TP | FP | FN | TN | review | Precision | Recall | F1 | **F2** | **EI(%)** |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| ① harness_norm_judge | 40 | 5 | 5 | 26 | 0 | 0.889 | 0.889 | 0.889 | **0.889** | **93.06** |
| ② ontology_policy | 25 | 0 | 20 | 15 | 16 | 1.000 | 0.556 | 0.714 | **0.610** | **98.61** |
| ③ ontology_policy_judge | 40 | 2 | 5 | 29 | 0 | 0.952 | 0.889 | 0.919 | **0.901** | **96.39** |

## 조건 설명

- **① harness_norm_judge** (`harness_norm_judge`): 가드+정규화(LLM)+judge(LLM) — LLM 중심
- **② ontology_policy** (`ontology_policy`): 기본 룰 가드(결정적 캐노니컬, judge 없음)
- **③ ontology_policy_judge** (`ontology_policy_judge`): 캐노니컬 + 필드전용 judge fallback

## EI 분해 (실무 재검토 시간)

| 조건 | 헛알람(FP) | AI+재검토(분) | EI(%) |
|---|--:|--:|--:|
| ① harness_norm_judge | 5 | 12.5 | 93.06 |
| ② ontology_policy | 0 | 2.5 | 98.61 |
| ③ ontology_policy_judge | 2 | 6.5 | 96.39 |
