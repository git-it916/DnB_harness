# 📚 김리나 — Docs · Literature Review · Communication

> 1학년이라고 위축될 필요 없어. 너의 트랙은 **학술제 발표의 얼굴**이고, 모든 멤버가 결과적으로 기댈 자리야.
> "팀이 만든 결과를 외부에 어떻게 보여줄 것인가" 가 너의 핵심 미션.
> 동시에 라벨링 페어워크로 도메인 지식도 빠르게 흡수 — **가장 빠르게 성장할 트랙**이기도 함.

---

## 1. 5분 컨셉

### Literature Review (선행 연구 조사)
"이미 비슷한 연구가 있나? 우리는 뭐가 다른가?" 를 정리하는 작업.
학술제 심사위원이 가장 먼저 묻는 질문: **"이거 누가 이미 해놓은 거 아니에요?"** → 답을 미리 준비.

### 핵심 검색 키워드 (영어가 결과 훨씬 많음)
- `LLM evaluation harness`
- `LLM hallucination detection`
- `prompt engineering compliance`
- `financial document AI`
- `due diligence automation LLM`
- `multimodal PDF understanding`

### 검색 채널
| 채널 | 무엇을 찾나 |
|------|-----------|
| Google Scholar | 학술 논문 (인용 수 보면서) |
| arXiv.org | 최신 LLM 논문 (CS.CL 카테고리) |
| GitHub trending | 비슷한 오픈소스 — 우리가 참고할 코드 |
| Anthropic/OpenAI Blog | 모델 회사 공식 가이드 |
| 금감원·금융위 사이트 | 한국 사모펀드 규제·가이드라인 |

### AEO vs SEO (네 관심사 연결)
- **SEO**: 검색엔진 최적화 — 키워드, 백링크
- **AEO (Answer Engine Optimization)**: ChatGPT·Perplexity 같은 AI가 우리 페이지를 인용하게 만드는 최적화
- 학술제 GitHub README도 이걸 의식해서 쓰면 외부 노출 ↑

### 라벨링 — 왜 1학년이 해도 되나?
사실 라벨링은 "PDF 읽고 사실 그대로 옮기기"라 도메인 지식보다 **꼼꼼함**이 중요. 시니어와 페어로 하면 도메인 지식도 같이 흡수됨.

---

## 2. 0주차 체크리스트

- [ ] [공통 README](./README.md) 0주차 셋업 완료
- [ ] `database/이지스 블랙ON 1호_준감필.pdf` 한 번 끝까지 읽어보기 (이해 안 가도 OK)
  - "어떤 항목들이 있구나" 정도면 충분
  - 모르는 용어는 메모해 둠 → 1주차에 정리할 거리
- [ ] PLAN.md 의 §3 (데이터) §4.3 (Risk Checklist) 정독
- [ ] GitHub README에 자기 이름 추가하는 PR 1개 만들어보기 (실습 목적)

---

## 3. 1주차: 선행 연구 5건 정리 + 용어 사전 초안

### 산출물 1: `docs/related-work.md` — 5건

각 항목 형식:

```markdown
<!-- docs/related-work.md -->
# 관련 연구 (Related Work)

## 1. RAGAS: Automated Evaluation of RAG (Es et al., 2023)
- **링크**: <https://arxiv.org/abs/2309.15217>
- **무엇을 했나**: RAG 시스템의 신뢰성·관련성·정답 충실도를 LLM으로 자동 평가하는 프레임워크
- **우리와의 연관**: 우리도 LLM 출력의 신뢰성 평가가 핵심. RAGAS의 "faithfulness" 메트릭은 우리 인용검증 가드와 유사한 아이디어.
- **우리가 다른 점**: RAGAS는 RAG 전용, 우리는 멀티모달 PDF + 가드 ablation 중심.

## 2. Constitutional AI (Anthropic, 2022)
- **링크**: <https://arxiv.org/abs/2212.08073>
...

## 3. ...
```

### 어디서 5건을 찾나? 추천 시작점:
1. **LLM 평가 일반**: "HELM" (Stanford), "BIG-bench" (Google) 키워드
2. **환각 검출**: "TruthfulQA", "FActScore" 검색
3. **금융 도메인 LLM**: "FinBERT", "BloombergGPT" 검색
4. **가드/제어**: "Guardrails AI", "NeMo Guardrails" 키워드
5. **한국어 LLM 평가**: "KMMLU", "HAERAE-bench" 검색

각 검색 결과의 abstract만 읽고 우리와 연관 깊은 5건 선정. 5건 너무 많으면 3건이라도.

### 산출물 2: `docs/glossary.md` — 펀드·LLM 용어사전

PDF 읽다가 모르는 용어 + 가이드 보면서 모르는 LLM 용어를 정리.
예시:

```markdown
<!-- docs/glossary.md -->
# 용어 사전 (Glossary)

## 펀드·금융 용어

### 집합투자업자 (Asset Management Company)
펀드를 운용하는 회사. 우리 케이스 = 이지스자산운용.

### 신탁업자 (Trustee)
펀드 자산을 보관하고 운용 지시를 집행하는 은행/증권사. 운용사와 별개 (자산 보호 목적).

### 운용보수 (Management Fee)
운용사가 받는 보수. 보통 연 0.5~2% 수준.

### 환매 (Redemption)
투자자가 펀드 지분을 돌려받는 것. 사모펀드는 환매 제한이 흔함.

### 우선순위 (Priority / Waterfall)
펀드 청산 시 누가 먼저 받는지 순서. 채권자 → 우선주 → 보통주 순.

## LLM·AI 용어

### Hallucination (환각)
LLM이 사실이 아닌 내용을 그럴듯하게 만들어내는 현상.

### Prompt Engineering
LLM에게 더 정확한 답을 받기 위한 입력 작성 기법.

### Tool Use / Function Calling
LLM이 미리 정의된 함수(또는 JSON 스키마)에 맞춰 답하도록 강제하는 기능.

... (10~15개 채우면 충분)
```

### DoD
- `docs/related-work.md` — 3~5건 정리
- `docs/glossary.md` — 10~15개 항목
- PR 1개 머지

---

## 4. 2주차: 라벨링 페어워크 + 발표 자료 outline

### 산출물 1: 라벨링 페어 세션 (승훈 또는 조건과)

승훈이 만든 `anchors.yaml` 템플릿에 같이 앉아서 10개 라벨링. 방식:
1. 둘이 따로 같은 항목 라벨링 (PDF 보고)
2. 답이 다른 항목만 토론 → 합의안 채택
3. "왜 모호했나" 기록 → 라벨링 가이드 보강

라벨링 가이드 예시:

```markdown
<!-- docs/labeling_guide.md -->
# 라벨링 가이드

## 원칙
1. **PDF에 적힌 그대로** — 추론 X, 외부 지식 X
2. 같은 값이 여러 문서에 있으면 가장 정식 문서를 source로
3. 못 찾으면 value: null + note: "못 찾음 (확인 필요)"

## 모호한 케이스 처리

### Case A: 운용보수가 "연 0.7% (분기별 0.175% 후취)" 라고 적힘
→ value: 0.7, unit: "percent_per_year", note: "분기 후취 방식, 본문 5p"

### Case B: 설정일이 "2025년 7월" 이라고만 적힘 (날짜 없음)
→ value: "2025-07", type: "year_month", note: "정확한 날짜 표기 없음"
```

### 산출물 2: 학술제 발표 outline (`docs/presentation_outline.md`)

```markdown
<!-- docs/presentation_outline.md -->
# 학술제 발표 — 슬라이드 outline (안)

## 슬라이드 구성 (12분 발표 가정, 12장)
1. 제목 + 팀 소개
2. **문제 정의** — 사모펀드 DD에서 LLM 신뢰성이 왜 문제인가
3. **연구 질문** — RQ1~RQ6 한 줄씩
4. **데이터** — 펀드 N개 × 3종 PDF + 골든셋
5. **방법: 하네스 구조도** — PDF → LLM → 가드 → 채점
6. **가드 5종 소개** — 각 가드가 뭘 잡는지 한 줄
7. **실험 결과 1: 베이스라인** — 모델별 F1 비교
8. **실험 결과 2: Ablation** ⭐ — 가드별 효과 막대그래프
9. **실험 결과 3: 비용·지연** — caching 효과
10. **한계** — 펀드 N개로 일반화 어디까지
11. **결론** — H1~H5 검증/기각 표
12. Q&A
```

### DoD
- 라벨링 10건 페어 완료
- `docs/labeling_guide.md` 모호 케이스 3개 이상 정리
- `docs/presentation_outline.md` 12장 골격

---

## 5. 막히면

| 증상 | 해결 |
|------|------|
| 검색해도 비슷한 연구 못 찾음 | 너무 좁게 검색 중. "LLM evaluation" 처럼 넓게 → 결과 보고 좁히기 |
| 영어 논문 abstract 이해 안 됨 | Claude/ChatGPT에 "이 abstract 한국어로 핵심만" 부탁. 단, 답을 그대로 옮기지 말고 자기 말로 다시 쓰기 |
| 라벨링 중 PDF 내용 이해 안 됨 | 페어 상대에게 즉시 질문. "이 줄 뭐예요?" 가 멍청한 질문이 아님 |
| 발표 outline 너무 일반적 | 우리 실험 결과 표 1장이라도 미리 넣어보면 구체화됨 |
| 문서 작성 톤이 어렵게 느껴짐 | 평소 친구한테 설명하듯 → 그 다음 어휘만 다듬기. 처음부터 "학술적으로" 쓰려고 하지 말 것 |

---

## 6. 다음에 참고할 것

- Google Scholar 사용법: 인용 수 기준 정렬, "Cited by" 클릭으로 후속 연구 따라가기
- arXiv 카테고리: `cs.CL` (Computation and Language), `cs.AI` 둘이면 충분
- 한국 학회 자료: KISS, RISS (한국학술정보) — 한글 논문 검색
- 발표 디자인: <https://slidesgo.com/>, <https://www.beautiful.ai/> — 무료 템플릿
- AEO 참고: "How to optimize for AI search engines" 같은 키워드 — 너의 강점을 GitHub README 가시화에 활용
