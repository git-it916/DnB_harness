# Project Status

최종 갱신: 2026-06-02

현재 단계: W2 진입 준비. 추출, 온톨로지, 가드의 초기 토대는 생겼고, 채점/CLI/실험 러너가 다음 병목이다. SHACL 비즈니스 제약은 보수 범위, 만기일 논리, 계약서 신탁업자 개수까지 보강됐다.

## 지금 시작할 곳

1. `src/scoring/` 구현 시작: `scorer.py`, `breakdown.py`, `compare.py`와 단위 테스트.
2. `src/cli/main.py` 골격 추가: `dnb run`, `dnb score`, `dnb compare` 진입점.
3. G3 SHACL 위임 연동 확인: 보강된 `ontology/shapes.ttl` 위반을 guard 조건에서 집행 신호로 사용.
4. `tests/golden/labeler_v1_rina.csv` 수집 및 골든셋 freeze 절차 진행.

## 모듈 상태

| 영역 | 상태 | 담당 | 다음 작업 | 기준 문서 |
|---|---|---|---|---|
| 온톨로지 TBox/ABox | 완료 | 종현 | G3 SHACL 위임 연동 확인 지원 | `docs/ARCHITECTURE.md` |
| Claude 추출 경로 | 완료 | 종현 | 회귀 테스트 유지 | `docs/INTERFACES.md` |
| Gemma 추출 경로 | 초기 구현 | 승훈 | IM 측 추출 정확도 검증 | `docs/reference/extract_guard_plan.md` |
| Guards | 초기 구현 | 승훈 | `tests/test_guards.py` 추가 | `docs/INTERFACES.md` |
| 골든셋 | 검수 중 | 리나/승훈 | 라벨러 검수, κ 합의, freeze | `docs/GOLDENSET.md` |
| Scoring | 미시작 | 승연 | 채점기와 메트릭 단위 테스트 | `docs/GOLDENSET.md` |
| CLI/실험 | 미시작 | 건 | CLI 골격과 3조건 runner | `docs/ROADMAP.md` |
| 통계 | 미시작 | 승훈/건 | McNemar, bootstrap CI 구현 | `docs/ROADMAP.md` |

## 완료로 보는 것

| 마일스톤 | 완료 기준 | 상태 |
|---|---|---|
| W1 인터페이스 합의 | 추출, 가드, 골든셋 형식 문서화 | 완료 |
| W1 추출 PoC | PDF에서 구조화 추출 결과 생성 | 완료 |
| W1 온톨로지 토대 | 4개념 TTL, ABox 매핑, 기본 SHACL 검증 | 완료 |
| W2 점수 리포트 | `score.json` 산출 | 미완료 |
| W2 골든셋 freeze | 30문항 검수와 κ 합의 | 미완료 |
| W3 3조건 실험 | baseline/ontology/guard 비교 실행 | 미완료 |

## 막힌 것

| 항목 | 영향 | 필요 결정/작업 |
|---|---|---|
| `src/scoring/` 부재 | 3조건 실험 결과를 점수화할 수 없음 | scorer 최소 구현 우선 |
| `src/cli/` 부재 | 팀원이 동일 명령으로 실행하기 어려움 | Typer 기반 CLI 골격 추가 |

## 문서 운영 원칙

- 상태 변화는 이 파일에만 반영한다.
- 설계 설명은 `ARCHITECTURE.md`, 경계와 스키마는 `INTERFACES.md`, 일정은 `ROADMAP.md`에 둔다.
- 날짜별 작업 기록은 `archive/`로 이동한다.
