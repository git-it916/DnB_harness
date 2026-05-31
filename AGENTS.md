# AGENTS.md

이 파일은 이 레포에서 사람과 AI agent가 같은 지도를 보고 작업하기 위한 진입점이다.
Claude Code 같은 agentic coding tool은 코드베이스를 이해하고, 반복 작업을 실행하고,
복잡한 코드를 설명하며, git workflow를 자연어로 도울 수 있다. 다만 이 레포에서는
아래 문서와 경계를 소스 오브 트루스로 삼고, 자동화보다 검증 가능성을 우선한다.

## 먼저 읽을 문서

1. `docs/STATUS.md` - 현재 완료 상태, 막힌 것, 다음 시작점
2. `docs/INTERFACES.md` - 깨면 안 되는 스키마와 모듈 경계
3. `docs/ARCHITECTURE.md` - 전체 하네스 설계와 용어
4. `docs/Role_Dividing.md` - 담당자별 책임과 협업 규칙
5. 필요한 작업별 runbook - 실행 명령과 산출물 위치

## 소스 오브 트루스

| 주제 | 위치 |
|---|---|
| 현재 상태와 다음 작업 | `docs/STATUS.md` |
| 전체 설계와 용어 | `docs/ARCHITECTURE.md` |
| 인터페이스와 스키마 | `docs/INTERFACES.md` |
| 골든셋 규칙 | `docs/GOLDENSET.md` + `tests/golden/golden_master.csv` |
| 역할과 책임 | `docs/Role_Dividing.md` |
| 일정과 마일스톤 | `docs/ROADMAP.md` |
| 디렉토리 구조 | `docs/tree.md` |
| 과거 작업 로그 | `docs/archive/` |

## Agent 작업 원칙

- 작업 시작 전 `docs/STATUS.md`에서 현재 병목과 다음 시작점을 확인한다.
- 코드 변경 전 관련 인터페이스를 `docs/INTERFACES.md`에서 확인한다.
- 용어가 헷갈리면 `docs/ARCHITECTURE.md`의 용어 사전을 따른다.
- 담당 영역과 협업 규칙은 `docs/Role_Dividing.md`를 따른다.
- 기존 패턴, 모듈 경계, 테스트 구조를 먼저 읽고 그 안에서 최소 변경한다.
- 자연어 요청을 바로 실행하되, 스키마·데이터·보안 경계가 흔들리면 먼저 확인한다.
- 코드 설명, 루틴 작업, git 보조는 가능하지만 최종 판단은 문서와 테스트 결과에 둔다.
- 플러그인, 커스텀 명령, 보조 agent를 쓰더라도 이 파일의 규칙과 레포 문서가 우선한다.

## 보안과 데이터

- `database/*.pdf`와 `.env`는 커밋하거나 외부 업로드하지 않는다.
- PDF 원문, 계약 데이터, 비밀값을 외부 서비스에 붙여 넣지 않는다.
- 로그와 리포트에 민감 정보가 들어가는지 확인한다.
- 버그 리포트나 외부 이슈 작성 시 재현 정보만 남기고 민감 데이터는 제거한다.

## 작업 규칙

- `main` 직접 push 금지. 브랜치에서 작업하고 PR로 합친다.
- 인터페이스 변경은 `docs/INTERFACES.md`와 관련 테스트를 함께 수정한다.
- 완료/진행/막힘 상태는 `docs/STATUS.md`에만 갱신한다.
- 과거 작업 기록은 `docs/archive/`에 보관하고 현재 지시 문서처럼 쓰지 않는다.
- 실행 방법이 새로 생기면 `docs/runbooks/`에 짧게 남긴다.
- 막히면 원인, 재현 명령, 필요한 결정을 정리해 PM에게 공유한다.

## 하네스 핵심 경계

- LLM 호출은 추출과 Judge에 한정한다. 가드와 채점기는 결정론 코드여야 한다.
- 가드는 G1 형식, G2 출처, G3 제약을 검사하며 LLM을 호출하지 않는다.
- 채점기는 순수 함수로 유지하고 골든셋 정답을 임의 변경하지 않는다.
- 온톨로지 변경은 `ontology/trust_fund.ttl`, `ontology/shapes.ttl`, 관련 테스트를 함께 본다.
- 인터페이스 이름, 필드, JSON schema는 팀 병렬 작업의 계약이므로 임의로 깨지 않는다.

## 검증 명령

```bash
uv run pytest
```

필요 시 더 좁은 테스트를 먼저 돌릴 수 있지만, 완료 전에는 관련 테스트를 통과시킨다.

## Definition of Done

- 관련 테스트가 통과한다.
- 인터페이스 변경 시 `docs/INTERFACES.md`가 갱신되어 있다.
- 완료 상태와 다음 작업이 `docs/STATUS.md`에 반영되어 있다.
- 새 명령이나 운영 절차가 생기면 `docs/runbooks/`에 문서화되어 있다.
