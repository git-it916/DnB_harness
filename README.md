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
| [`docs/PLAN.md`](./docs/PLAN.md) | 설계 — 무엇을·왜 |
| [`docs/실행계획.md`](./docs/실행계획.md) | 실행 — 누가·언제 (4주) |
| [`docs/역할분담.md`](./docs/역할분담.md) | 역할·책임·RACI |
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

---

## 팀

| 역할 | 담당 |
|------|------|
| PM · 통계 · 보고 | 신승훈 |
| 온톨로지 · LLM 추출 | 노종현 |
| 가드 · 하네스 · 실험 | 조건 |
| 검증 · 비교 | 한승연 |
| 골든셋 검수 · 발표 | 김리나 |
