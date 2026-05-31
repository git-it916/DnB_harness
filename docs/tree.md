# Project Tree

최종 갱신: 2026-05-31

이 문서는 디렉토리 역할을 빠르게 찾기 위한 지도다. 현재 진행 상태와 다음 작업은 `docs/STATUS.md`를 기준으로 본다.

## 루트

| 경로 | 역할 |
|---|---|
| `AGENTS.md` | 팀원과 AI agent 공통 작업 지도 |
| `README.md` | 프로젝트 소개, 빠른 시작, 문서 입구 |
| `pyproject.toml` / `uv.lock` | Python 패키지와 의존성 |
| `.env` | 로컬 API 키. 커밋 금지 |
| `database/` | 펀드 PDF 원본. 외부 업로드 금지 |
| `reports/` | 실행 산출물. 자동 생성 중심 |

## 문서

| 경로 | 역할 |
|---|---|
| `docs/README.md` | 문서 목차 |
| `docs/STATUS.md` | 현재 상태와 다음 시작점 |
| `docs/ARCHITECTURE.md` | 전체 하네스 설계 |
| `docs/INTERFACES.md` | 스키마와 모듈 경계 |
| `docs/GOLDENSET.md` | 골든셋 작성 규칙 |
| `docs/ROADMAP.md` | 4주 실행 계획 |
| `docs/Role_Dividing.md` | 역할과 책임 |
| `docs/runbooks/` | 실행 방법 |
| `docs/reference/` | 긴 설계 노트와 상세 설명 |
| `docs/archive/` | 과거 작업 로그 |
| `docs/decisions/` | 구조 결정 기록 |

## 코드

| 경로 | 역할 |
|---|---|
| `src/client/` | LLM SDK/Ollama 클라이언트 |
| `src/schemas/` | Pydantic 추출 스키마 |
| `src/ingest/` | PDF/이미지 입력 처리 |
| `src/extraction/` | Gemma 추출 백엔드와 side schema |
| `src/pipelines/` | Claude 추출, 정규화, 교차검증, judge |
| `src/guards/` | G1 형식, G2 출처, G3 제약 가드 |
| `src/ontology/` | JSON to ABox 매핑과 SHACL 검증 |
| `src/scoring/` | 채점기 예정 위치 |
| `src/cli/` | CLI 예정 위치 |
| `src/stats/` | 통계 검정 예정 위치 |

## 테스트와 데이터

| 경로 | 역할 |
|---|---|
| `tests/` | pytest 테스트 |
| `tests/golden/golden_master.csv` | 골든셋 마스터 |
| `ontology/trust_fund.ttl` | TBox 개념 정의 |
| `ontology/shapes.ttl` | SHACL 규칙 |
| `prompts/v0/` | 버전 관리되는 프롬프트 |
| `scripts/` | smoke, PoC, 렌더링, 실험 보조 스크립트 |

## 유지 규칙

- 새 핵심 디렉토리를 추가하면 이 파일을 갱신한다.
- 상태 변화는 이 파일이 아니라 `docs/STATUS.md`에 적는다.
- 자동 생성 파일과 비밀 정보는 커밋하지 않는다.
