# 3조건 비교 (n=30, golden=v0.1, model=gemma4:31b, seed=?)

## 핵심 지표

| 조건 | Accuracy | Precision | Recall ★ | F1 | 환각률 |
|---|--:|--:|--:|--:|--:|
| ② +ontology | 0.462 | 0.462 | 1.000 | 0.632 | 0.000 |
| ③ +guard | 0.462 | 0.462 | 1.000 | 0.632 | 0.000 |

## 통계 (Stage D)

- McNemar p-value (③ vs ①): __
- Bootstrap 95% CI on F1 (③): [__, __]

## 난이도별 Recall

| 난이도 | ② +ontology | ③ +guard |
|---|--:|--:|
| easy | 0.000 | 0.000 |
| medium | 1.000 | 1.000 |
| hard | 1.000 | 1.000 |

