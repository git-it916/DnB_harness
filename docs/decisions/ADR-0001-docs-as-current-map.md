# ADR-0001: Docs as Current Map

Date: 2026-05-31

## Status

Accepted

## Context

문서가 `now/`, `past/`, 루트 파일에 섞이면서 현재 상태, 과거 로그, 설계 초안이 같은 중요도로 보였다. 팀원이 어디까지 완료됐고 어디서 시작해야 하는지 판단하기 어려웠다.

## Decision

현재 상태는 `docs/STATUS.md` 하나에만 둔다. 설계, 인터페이스, 골든셋, 일정, 역할은 각각 독립 문서로 승격하고, 과거 작업 로그는 `docs/archive/`로 이동한다. 긴 설계 노트는 `docs/reference/`로 낮춘다.

## Consequences

- 팀원과 AI agent는 `AGENTS.md`와 `docs/STATUS.md`에서 시작한다.
- 문서 중복은 줄어들지만, 상태 변경 시 `STATUS.md`를 갱신하는 운영 습관이 필요하다.
- 기존 링크는 새 파일명에 맞춰 지속적으로 정리해야 한다.
