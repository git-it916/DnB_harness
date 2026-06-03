# Project Status

최종 갱신: 2026-06-03

현재 단계: 검증 엔진 + 평가/증명 레이어 구현 완료, **3조건(non-harness/harness/harness+norm) 비교 실측 완료(잠정 골든)**. 추출·온톨로지·가드에 더해 채점(`src/scoring`)·CLI(`src/cli`)·하네스 러너(`src/harness`)·통계(`src/stats`)가 동작한다. `ontology_policy` 결정론 canonical comparison 경로가 추가되었고, `ontology_policy_judge`는 Claude normalization 없이 policy 허용 필드에만 judge fallback을 적용한다. 다음 병목은 골든셋 freeze 와 ontology_policy_judge 실측 비교.

## 지금 시작할 곳

1. 골든셋 freeze: `tests/golden/labeler_v1_rina.csv` 수집 → κ 합의 → `golden_master.csv` 동결.
2. ontology_policy_judge 실측: `python scripts/score_ontology_policy.py` 실행 후 harness+norm 대비 C021 및 의미동등 케이스 성능 비교.
3. 정규화/judge 의 의미동등 오탐 4건(C002/C006/C007/C018) 프롬프트 개선.
4. `GOLDENSET.md §7` FN/TN 정의에 `pred=missing` 포함 비준 (PM).

## 모듈 상태

| 영역 | 상태 | 담당 | 다음 작업 | 기준 문서 |
|---|---|---|---|---|
| 온톨로지 TBox/ABox | 완료 | 종현 | 유지 | `docs/ARCHITECTURE.md` |
| Claude 추출 경로 | 완료 | 종현 | 회귀 테스트 유지 | `docs/INTERFACES.md` |
| Gemma 추출 경로 | 완료 | 승훈 | IM 측 추출 정확도 검증 | `docs/reference/extract_guard_plan.md` |
| Guards | 완료 | 승훈 | (G3 천분율/대괄호 파싱 보강 완료) | `docs/INTERFACES.md` |
| Scoring | 완료 | 승연 | baseline 채점 경로 연결 | `docs/runbooks/scoring.md` |
| CLI | 완료 | 건 | `dnb run/score/compare/stats` | `docs/runbooks/reproduce-results.md` |
| 하네스 러너 (3조건) | 완료 | 건/PM | baseline 라이브 채점 | `docs/INTERFACES.md` §4 |
| 통계 | 완료 | 승훈/건 | baseline vs guard McNemar | `docs/runbooks/reproduce-results.md` |
| 골든셋 | 검수 중 | 리나/승훈 | 라벨러 검수, κ 합의, freeze | `docs/GOLDENSET.md` |

## 완료로 보는 것

| 마일스톤 | 완료 기준 | 상태 |
|---|---|---|
| W1 인터페이스 합의 | 추출, 가드, 골든셋 형식 문서화 | 완료 |
| W1 추출 PoC | PDF에서 구조화 추출 결과 생성 | 완료 |
| W1 온톨로지 토대 | 4개념 TTL, ABox 매핑, 기본 SHACL 검증 | 완료 |
| W2 점수 리포트 | `score.json` 산출 | 완료 |
| W2 골든셋 freeze | 30문항 검수와 κ 합의 | 미완료 |
| W3 3조건 실험 | baseline/ontology/guard 비교 실행 | 완료 (잠정 골든) — non-harness/harness/harness+norm 실측, `runbooks/reproduce-results.md §6` |
| Ontology policy 비교 | field policy canonical comparison + 제한적 judge fallback | 구현 완료, judge 실측 대기 — `runbooks/reproduce-results.md §7` |

## 막힌 것

| 항목 | 영향 | 필요 결정/작업 |
|---|---|---|
| 골든셋 freeze 미완 | 발표용 통계가 잠정값 | 라벨러 검수 + κ ≥ 0.7 합의 |
| ontology_policy_judge 실측 미완 | 새 policy 경로가 harness+norm 대비 얼마나 개선되는지 미확정 | `ANTHROPIC_API_KEY` 환경에서 `scripts/score_ontology_policy.py` 실행 후 비교 |

## 검증 현황 (참고)

- 테스트: `pytest` **108 passed** (canonical policy/parser/compare/pipeline 및 ontology_policy scoring 경로 포함).
- 라이브 풀런: `gemma4:31b` guard 모드 174s/24,168토큰, shacl_conforms=True (`database/gemma4_harness/`).
- 3조건 비교(잠정 골든): ① non-harness F1=0.762(R0.667) · ② harness F1=0.632(R1.000) · ③ harness+norm **F1=0.815**(R0.917). McNemar ①vs② p=0.049.
- 결정론 ontology_policy: P=0.600 · R=1.000 · F1=0.750 (`python -m src.cli score --mode ontology_policy`).

## 문서 운영 원칙

- 상태 변화는 이 파일에만 반영한다.
- 설계 설명은 `ARCHITECTURE.md`, 경계와 스키마는 `INTERFACES.md`, 일정은 `ROADMAP.md`에 둔다.
- 실행 절차는 `runbooks/`, 날짜별 작업 기록은 `archive/`로 이동한다.
