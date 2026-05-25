# DnB Harness — PLAN

> 한양대 D&B 학술제 7팀 · LLM Due-Diligence Evaluation Harness for Korean Private Placement Funds

---

## 0. 한 줄 요약 — 우리는 무엇을 검증하는가

> **"한국 사모펀드 3종 문서 묶음(핵심상품설명서·투자제안서·신탁계약서)을 멀티모달 LLM에 PDF 그대로 던졌을 때, 인간 애널리스트 수준의 Due Diligence를 할 수 있는가?"**
>
> 더 좁히면 두 가지 능력에 집중한다:
> 1. **Cross-document 일관성 검증** — 3종 문서가 같은 펀드를 가리키지만 항목(수수료·만기·자산구성·해지·환매·우선순위 등)이 서로 어긋나는 케이스를 찾아내는가.
> 2. **리스크 조항 식별** — 표준 리스크 체크리스트의 각 항목이 어느 문서·어느 조항에 어떻게 표현되어 있는지 정확히 매핑하는가.
>
> 이 하네스의 산출물은 **모델 선택 의사결정에 쓸 수 있는 정량 지표**(정확도·비용·지연)와 **재현 가능한 평가 파이프라인**이다. "Claude가 잘하더라"가 아니라 "Sonnet 4.6은 텍스트 PDF에서 일관성 검증 recall 0.91, 스캔 포함 시 0.74, 단가 $0.12/펀드" 같은 수치가 목표.

---

## 1. 검증 대상 질문 (Research Questions)

| # | 질문 | 측정 방식 | 의사결정 영향 |
|---|------|-----------|--------------|
| RQ1 | 각 문서에서 핵심 사실(수수료·만기·운용사·신탁업자·기준가·목표수익률 등)을 정확히 추출하는가? | 앵커 사실 GT 대비 Exact Match / F1 | 단순 추출 태스크에 LLM 충분한지 |
| RQ2 | 3개 문서 간 모순(예: 수수료 0.7% vs 0.75%, 만기 2030-07 vs 2030-12)을 탐지하는가? | 합성 perturbation에 대한 detection precision/recall, false-alarm rate | 본 하네스의 핵심 능력 검증 |
| RQ3 | 표준 리스크 체크리스트(15~20개 카테고리)의 각 항목을 정확히 매핑하는가? | 항목별 P/R + Cohen's κ(인간 라벨러 2명 vs LLM) | 리스크 리포트 자동화 가능성 |
| RQ4 | 스캔본(신탁계약서) 포함 여부에 따른 성능 저하 폭은? | 텍스트-only vs 텍스트+스캔 분리 측정, OCR 사전처리와 비교 | OCR 파이프라인 필요 여부 결정 |
| RQ5 | 모델별 (Opus 4.7 / Sonnet 4.6 / Haiku 4.5) accuracy-cost-latency tradeoff는? | 동일 eval suite, 모델만 교체, 단가·p50/p95 lat·accuracy | 운영 모델 선정 |
| RQ6 | Prompt caching이 운영 단가를 충분히 낮추는가? | 캐시 적용 전후 cost/eval, cache hit rate | 펀드당 다중 쿼리 운영 가능성 |

---

## 2. 기본 가설 (Hypotheses)

가설은 **사전 등록(pre-register)** 한다. 실험 결과로 검증/기각하며, 사후 합리화 금지.

- **H1 (추출 정확도)**: Sonnet 4.6은 텍스트 기반 PDF의 앵커 사실에 대해 F1 ≥ 0.95.
- **H2 (스캔 robustness)**: 스캔 PDF가 포함된 항목의 일관성 탐지 recall은 텍스트-only 대비 10%p 이상 감소.
- **H3 (캐시 경제성)**: 펀드당 두 번째 쿼리부터 입력 비용 ≥ 90% 절감 (3개 PDF가 캐시 대상).
- **H4 (모델 격차)**: Risk checklist 매핑에서 Opus가 Haiku 대비 macro-F1 ≥ 5%p 우위, 다만 Haiku 단가가 1/10 미만이면 운영에서는 Haiku 채택이 합리적.
- **H5 (false-alarm)**: 일관성 탐지에서 perturbation 없는 정상 펀드에 대한 false-positive rate ≤ 0.05 (애널리스트 시간 낭비 방지).

---

## 3. 데이터 (Dataset)

### 3.1 현재 보유분
- **이지스 블랙ON 1호** (1 펀드)
  - `핵심상품설명서` (텍스트 PDF, 준감필 버전)
  - `투자제안서` (텍스트 PDF, 준감필 버전)
  - `제정신탁계약서` (스캔 이미지 PDF, 날인본 2025-07-22)
- 위치: `database/` (gitignore — 비공개 자료)

### 3.2 확장 계획
- 목표: 약 10개 펀드. 우선 같은 운용사 시리즈(동질성)로 5개 수집 후, 다른 운용사·자산군으로 다양화.
- 수집 우선순위:
  1. 텍스트 PDF + 텍스트 PDF + 스캔(우리 케이스와 동형) — 일반화 검증
  2. 텍스트 3종 (스캔 변수 통제) — RQ4 비교군
  3. 스캔 비중 다른 펀드 (강건성)

### 3.3 라벨링
- 펀드당 **앵커 사실 25~35개** 수기 라벨 (펀드명·운용사·신탁업자·설정일·만기·기준가·수수료 3종·환매조건·해지조건·우선순위·자산구성 5종 등).
- 라벨러 2명 → 디스크립트 비교 → 불일치 항목 토론으로 합의 (κ 사전 측정).
- 라벨 포맷: `database/labels/<fund_id>/anchors.yaml`.

---

## 4. 평가 컴포넌트 (Eval Components)

5개 우선 항목을 다음과 같이 구성한다.

### 4.1 Anchor Facts Ground Truth
- 위 3.3에서 만든 YAML을 정답으로, LLM의 구조화 JSON 출력과 항목별 매칭.
- 매칭 방식: 숫자/날짜/금액은 normalize 후 exact, 자유 텍스트는 BLEU 대신 fuzzy match(타깃 ≥ 0.85)와 인간 spot-check 병용.

### 4.2 Synthetic Perturbation (RQ2 핵심)
- **목표**: 자연 발생 모순이 드무므로(어차피 같은 펀드 문서니까), 의도적으로 한 문서에 미세 수정을 주입해 "탐지 가능 여부" 평가.
- **방법**:
  - 텍스트 PDF: `pymupdf`로 페이지 텍스트 span 찾고 redaction 후 동일 폰트로 변조 텍스트 overlay.
  - 스캔 PDF: 페이지 이미지에 새 텍스트 박스 합성(흰 배경 사각 + 한글 폰트 렌더).
- **perturbation 카테고리** (각 5~10개 샘플):
  1. **숫자 변조** — 수수료 0.7%→0.75%, 만기 2030-07-31→2030-12-31
  2. **명칭 변조** — 신탁업자 명 1글자 교체
  3. **조항 누락** — 한 문서에서만 환매제한 조항 1개 삭제
  4. **조항 추가** — 한 문서에만 비표준 우선순위 조항 추가
  5. **단위 변조** — 억 ↔ 백만, 연 ↔ 분기
- **컨트롤**: perturbation 없는 원본도 동일 분량 섞어서 false-alarm 측정.
- **출력**: `(fund_id, perturbation_id, doc_target, field, original→altered)` 와 LLM 판정 비교.

### 4.3 Risk Checklist (RQ3)
- 체크리스트는 금감원 사모펀드 설명서 가이드라인 + 표준 약관을 베이스로 자체 정리한 15~20개 항목 (예: 환매 제한, 손실 우선 흡수 구조, 운용보수 변경 조항, 키맨 조항, 자기거래, 이해상충, 보고 의무, 평가 방법 등).
- 각 항목에 대해 LLM이 `{ exists: bool, evidence: { doc, page, span }, severity: low|med|high }` 반환.
- 라벨러가 동일 스키마로 GT 작성 → 항목별 P/R + κ.

### 4.4 Structured JSON Output
- 모든 LLM 호출은 **JSON Schema 또는 Pydantic 스키마**에 묶음 (Anthropic tool-use 또는 prefill).
- 스키마 위반 = 자동 실패로 집계, 재시도 정책(`tenacity` 2회) 별도 기록.
- 스키마는 `src/schemas/` 에 버전 관리, 모든 eval 실행에 schema_version 기록(재현성).

### 4.5 Prompt Caching Strategy
- **레이아웃**: `[system prompt(고정)] + [3개 PDF document blocks(고정, cache_control: ephemeral)] + [태스크별 user message(변동)]`.
- **타겟**: 펀드당 N개 쿼리(앵커 추출 + 일관성 + 리스크 = 3개 메인 쿼리 + perturbation N개) → 첫 쿼리에서만 PDF full price, 이후 캐시 히트.
- **측정**: 응답의 `usage.cache_creation_input_tokens`, `cache_read_input_tokens` 로깅, eval당 실효 단가 계산.
- **운영 한계**: 캐시 5분 TTL — eval 배치 내에서는 한 펀드 쿼리들을 연속으로 묶어 실행(스케줄러 책임).

---

## 5. 메트릭 (Metrics)

| 영역 | 메트릭 | 임계치(stretch) |
|------|--------|---------------|
| 추출 (RQ1) | macro-F1, EM | F1 ≥ 0.95 (텍스트), ≥ 0.85 (스캔) |
| 일관성 (RQ2) | detection P/R/F1, false-alarm rate | recall ≥ 0.85, FAR ≤ 0.05 |
| 리스크 (RQ3) | 항목별 P/R, macro-F1, Cohen's κ (LLM vs human) | κ ≥ 0.70 |
| 스키마 (4.4) | schema-valid rate, retry rate | ≥ 0.99 |
| 비용 (RQ6) | $/펀드, $/쿼리, cache hit rate | hit rate ≥ 0.80 (2nd+ query) |
| 지연 (RQ5) | p50/p95 latency per query | p95 ≤ 30s (Sonnet) |

리포트는 `pandas` long-format → `reports/<run_id>/` 아래 markdown + figures 자동 생성.

---

## 6. 아키텍처 (Architecture)

```
DnB_harness/
├── database/              # PDFs (gitignored) + labels/
│   └── labels/<fund_id>/  # anchors.yaml, risks.yaml
├── src/
│   ├── schemas/           # pydantic 모델: AnchorFacts, ConsistencyReport, RiskAssessment
│   ├── client/            # anthropic 래퍼 (caching, retry, usage logging)
│   ├── perturb/           # pymupdf 기반 perturbation 생성기
│   ├── eval/              # 4.1~4.3 scorer
│   ├── pipelines/         # 펀드 1개 처리 (load→prompt→parse→score)
│   └── cli.py             # typer 진입점: run / perturb / score / report
├── prompts/               # 시스템 프롬프트 + few-shot (버전 관리)
├── reports/<run_id>/      # 결과물 (자동 생성)
├── tests/                 # pytest: 스키마, scorer, perturbation invariant
├── PLAN.md
├── requirements.txt
└── .env.example           # ANTHROPIC_API_KEY
```

**설계 원칙**:
- 모든 LLM 호출은 `(prompt_version, schema_version, model, fund_id, run_id)` 로 식별 가능.
- 결정론 확보 안 되는 부분(LLM 출력)은 raw 응답 전체를 `reports/<run_id>/raw/` 에 저장 — 사후 재채점 가능.
- Scorer는 LLM 호출 없이 순수 함수로 구현 (재현성·테스트 용이).

---

## 7. 단계별 마일스톤 (Phased Milestones)

각 단계는 **검증 가능한 산출물**로 종료한다.

### Phase 0 — 인프라 (1주)
- [x] conda env `dnb_harness` + requirements.txt
- [ ] `.env.example` + Anthropic API 연결 smoke test
- [ ] PDF 3종 로딩 → Claude 1회 호출 → JSON 응답 파싱 end-to-end 동작
- **DoD**: `python -m src.cli smoke --fund igis_blackon_1` 통과

### Phase 1 — 단일 펀드 파이프라인 (1~2주)
- 앵커 사실 라벨 25~35개 (이지스 블랙ON 1호) 수기 작성
- AnchorFacts/Consistency/Risk 스키마 확정
- Sonnet 4.6로 베이스라인 측정 (RQ1, RQ3 1차)
- **DoD**: 베이스라인 리포트 1부 (markdown + figures), schema-valid rate ≥ 0.95

### Phase 2 — Perturbation 프레임워크 (1~2주)
- `pymupdf` 기반 텍스트 PDF perturbation 생성기 (카테고리 1~5)
- 스캔 PDF perturbation은 Phase 2.5로 분리 (난이도 높음)
- 펀드 1개 × perturbation 20~30개 생성, 시각 검증 100%
- RQ2 1차 측정 (텍스트 PDF만)
- **DoD**: perturbation set + RQ2 결과 표

### Phase 3 — 모델 비교 & 캐싱 (1주)
- Opus 4.7 / Sonnet 4.6 / Haiku 4.5 동일 eval suite 실행
- Prompt caching on/off A/B
- **DoD**: 모델 × 메트릭 비교표, cost-accuracy 산점도

### Phase 4 — 스케일 (3~4주)
- 펀드 9개 추가 수집·라벨링
- 전체 eval 1회 + 분석 리포트
- 일반화 (펀드 간 variance) 평가
- **DoD**: 최종 리포트 (학술제 발표 자료 기반)

### Phase 2.5 — 스캔 perturbation (옵션, 시간 허락 시)
- 스캔본 perturbation으로 RQ4 본격 검증

---

## 8. 리스크 & 가정 (Risks & Assumptions)

| # | 리스크 | 영향 | 완화 |
|---|--------|------|------|
| R1 | 펀드 PDF 수집 난항(비공개·NDA) | Phase 4 지연 | 학회·운용사 네트워크 활용, 공시된 펀드(증권신고서 첨부)로 대체 가능성 |
| R2 | 스캔 PDF의 한글 폰트 한계로 LLM OCR 정확도 낮음 | RQ4 결론 약화 | 외부 OCR(Naver Clova OCR 등)과 비교 대조군 추가 |
| R3 | Perturbation이 너무 부자연스러워 LLM이 "조작 흔적"으로 탐지 | RQ2 결과가 양성 편향 | 시각 검증 + 폰트/위치 정렬, blind 인간 spot-check |
| R4 | Cache 5분 TTL로 배치 외 호출 시 캐시 미스 | 비용 가정 무너짐 | 배치 스케줄러로 펀드별 쿼리 연속 실행 강제 |
| R5 | 라벨러 1인이라 IAA(κ) 측정 불가 | RQ3 신뢰도 ↓ | 최소 핵심 30 항목은 2인 라벨, 나머지는 spot-check |
| R6 | Anthropic SDK·모델 사양 변경 | 재현성 ↓ | 모든 run에 `anthropic.__version__`, 모델 id 기록 |

**가정**:
- A1: ANTHROPIC_API_KEY 사용 가능, 학술제 기간 동안 충분한 크레딧 확보.
- A2: 학술제 발표일까지 최소 펀드 3~5개는 확보 가능.
- A3: 사모펀드 PDF의 외부 공유는 팀 내부에서만, 어떤 리포지토리·외부 서비스에도 업로드하지 않음 (NDA 가정).

---

## 9. 산출물 (Deliverables)

1. **재현 가능한 평가 하네스** — `python -m src.cli run --suite all --fund <id>` 한 번에 전체 실행.
2. **펀드별 리스크 리포트 샘플** — DD 분석가가 그대로 활용 가능한 markdown/PDF.
3. **모델 선정 가이드** — Opus/Sonnet/Haiku tradeoff 표 + 우리 use-case 추천.
4. **학술제 발표 자료** — RQ별 결론·한계·후속 연구.

---

## 10. 다음 단계 (Immediate Next Actions)

1. `.env.example` 작성 + API smoke test 스크립트
2. Pydantic 스키마 v0 (`AnchorFacts`, `ConsistencyReport`, `RiskAssessment`) 초안
3. 이지스 블랙ON 1호 앵커 사실 라벨링 (스프레드시트 → YAML 변환)
4. PDF document block + prompt caching 동작하는 최소 호출 코드 (`src/client/anthropic_client.py`)

> **운영 원칙**: 매 Phase 끝에 PLAN.md를 업데이트(가설 검증/기각 표시), 결과는 `reports/`에 누적. PLAN은 살아있는 문서.
