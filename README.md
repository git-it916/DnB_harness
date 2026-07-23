# 🛡️ DnB Harness

> **온톨로지 기반 신탁계약서 검증 하네스** — 사모펀드 신탁계약서가 제대로 작성됐는지, 그 내용이 투자제안서(IM)에 정확히 반영됐는지 LLM으로 검증하고, 그 판단을 **얼마나 믿을 수 있는지 통계로 증명**한다.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="LLM" src="https://img.shields.io/badge/Claude-multimodal%20PDF-D97757">
  <img alt="Ontology" src="https://img.shields.io/badge/Ontology-rdflib%20%2B%20pyshacl-4B8BBE">
  <img alt="Status" src="https://img.shields.io/badge/status-MVP%20(4주)-success">
</p>

한양대학교 D&B 학술제 7팀

---

## 핵심 아이디어

AI가 신탁계약서를 그냥 읽게 두면 **없는 조항을 지어내거나(환각)** **모순을 놓친다**. 그래서:

1. **온톨로지(개념 지도)** 로 그라운딩 — 핵심 4개념(펀드·당사자·보수·환매)을 정해진 틀로 박아 누락·모순을 결정론적으로 탐지
2. **하네스(가드 3종)** 로 출력을 한 번 더 검증 — 형식·출처·제약
3. **3조건 비교**로 효과를 통계로 증명

```
PDF 3종 → [추출] → [온톨로지 변환] → [가드 3종] → [SHACL 적정성 + 교차검증] → [채점] → 리포트
```

| 조건 | 온톨로지 | 가드 | → 측정 |
|------|:---:|:---:|--------|
| ① 베이스라인 | ✗ | ✗ | 골든셋 30문항으로 |
| ② +온톨로지 | ✓ | ✗ | 불일치 탐지가 |
| ③ +가드(완성형) | ✓ | ✓ | 좋아지는지 (McNemar·부트스트랩) |

---

## 문서

| 문서 | 내용 |
|------|------|
| [`AGENTS.md`](./AGENTS.md) | 팀원·AI agent 공통 작업 지도 |
| [`docs/STATUS.md`](./docs/STATUS.md) | 현재 완료 상태와 다음 시작점 |
| [`docs/README.md`](./docs/README.md) | 문서 지도 |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | 설계 — 무엇을·왜 |
| [`docs/ROADMAP.md`](./docs/ROADMAP.md) | 실행 — 누가·언제 (4주) |
| [`docs/Role_Dividing.md`](./docs/Role_Dividing.md) | 역할·책임·RACI |
| [`docs/tree.md`](./docs/tree.md) | 디렉토리 구조 가이드 |

---

## 빠른 시작

```bash
# 1. 환경
uv sync --dev

# 2. API 키 (.env, git 커밋 금지)
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 3. 연결 확인
uv run python scripts/hello_claude.py

# 4. 테스트
uv run pytest
```

> ⚠️ `database/*.pdf`(펀드 자료)와 `.env`는 **절대 커밋·외부 업로드 금지**.

## 로컬 검토 웹

```bash
cd web && pnpm install && pnpm build && cd ..
uv run python -m src.web_api
```

`http://127.0.0.1:8000`에서 계약서와 IM을 업로드해 14개 필드 판정, 원문 근거,
가드·canonical 경로를 확인할 수 있다. 약칭·엔티티명처럼 자동 확정하기 어려운 항목은
사용자가 `같음 / 다름 / 판단 보류`로 결정하며, 명시적으로 선택한 경우에만 로컬 Alias로
기억한다. 상세 절차는 [`docs/runbooks/local-web.md`](./docs/runbooks/local-web.md)를 따른다.

---

## 팀

| 역할 | 담당 |
|------|------|
| PM · 추출(Gemma) · 가드 · 통계 | 신승훈 |
| 온톨로지 · LLM 추출(Claude) · 교차검증 | 노종현 |
| CLI · 변조 · 3조건 실험 · 부트스트랩 | 조건 |
| 검증 · 비교 | 한승연 |
| 골든셋 검수 · 발표 | 김리나 |
