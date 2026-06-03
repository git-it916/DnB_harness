# Documentation Map

이 디렉토리는 현재 작업에 필요한 문서와 과거 기록을 분리한다. 어디서 시작해야 할지 애매하면 `STATUS.md`를 먼저 본다.

## 매일 보는 문서

| 문서 | 역할 |
|---|---|
| [`STATUS.md`](./STATUS.md) | 현재 완료 상태, 다음 시작점, 막힌 것 |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 하네스 전체 설계, 용어, 파이프라인 |
| [`INTERFACES.md`](./INTERFACES.md) | ExtractionResult, Guard, score, manifest 스키마 |
| [`GOLDENSET.md`](./GOLDENSET.md) | 골든셋 CSV 컬럼, enum, 라벨링 규칙 |
| [`ROADMAP.md`](./ROADMAP.md) | 4주 실행 계획과 마일스톤 |
| [`Role_Dividing.md`](./Role_Dividing.md) | 팀원별 책임과 RACI |
| [`tree.md`](./tree.md) | 실제 디렉토리 구조 가이드 |

## 실행 가이드

| 문서 | 역할 |
|---|---|
| [`runbooks/local-setup.md`](./runbooks/local-setup.md) | 로컬 환경 준비 |
| [`runbooks/run-extraction.md`](./runbooks/run-extraction.md) | PDF 추출 실행 |
| [`runbooks/scoring.md`](./runbooks/scoring.md) | 채점기 작업 기준 |
| [`runbooks/run-experiment.md`](./runbooks/run-experiment.md) | 3조건 실험 실행 기준 |
| [`runbooks/reproduce-results.md`](./runbooks/reproduce-results.md) | 채점·통계·라이브 하네스 결과 재현 절차 (실측 포함) |

## 참고와 기록

| 위치 | 역할 |
|---|---|
| [`reference/`](./reference/) | 긴 설계 노트와 파이프라인 상세 |
| [`decisions/`](./decisions/) | 스코프나 구조 결정 기록 |
| [`archive/`](./archive/) | 날짜별 작업 로그 |
| [`ontology_prd.md`](./ontology_prd.md) | 초기 온톨로지 추출 PRD |

## 유지 규칙

- 현재 상태는 `STATUS.md`에만 적는다.
- 새 스키마나 모듈 계약은 `INTERFACES.md`에 먼저 반영한다.
- 작업 로그는 `archive/`로 보내고 현재 문서에서 중복 설명하지 않는다.
- 문서를 옮기면 `README.md`, `AGENTS.md`, 내부 링크를 같이 고친다.
