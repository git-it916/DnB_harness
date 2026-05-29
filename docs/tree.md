# 📂 프로젝트 디렉토리 트리 (한글 주석)

> 한양대 D&B 학술제 7팀 · DnB Harness · 최종 갱신 2026-05-29 (**MVP 스코프**)
> 설계 [`PLAN.md`](./PLAN.md) + 실행 [`실행계획.md`](./실행계획.md) + 역할 [`역할분담.md`](./역할분담.md) + 골든셋 [`golden_master.md`](./golden_master.md) 기준.
> 각 파일 옆 표시 — `✅` 이미 있음 / `📝` 곧 만들 것 / `🚫` git 제외 / `🤖` 자동 생성

---

## 1. 전체 트리

```
DnB_harness/
│
├── .gitignore                                   ✅  PDF·.env·reports/ 등 제외 룰
├── LICENSE                                      ✅  라이선스
├── README.md                                    ✅  프로젝트 한 줄 소개 + 팀
├── pyproject.toml                               ✅  uv 패키지 정의
├── uv.lock                                      ✅  의존성 락
├── requirements.txt                             ✅  (참고용 정적 목록)
├── .env                                         🚫  ANTHROPIC_API_KEY (각자 작성, gitignore)
│
├── database/                                    ✅  펀드 PDF 원본 (🚫 외부 공유 금지)
│   ├── 이지스 블랙ON 1호_준감필.pdf              ✅  투자제안서(IM) — 디지털 PDF
│   └── 제정신탁계약서_날인본_…_최종버전.pdf       ✅  신탁계약서 — 스캔 이미지 PDF (교차검증 기준)
│
├── ontology/                                    ✅  온톨로지 (rdflib + pyshacl)
│   ├── trust_fund.ttl                           ✅  코어 4개념 정의: 펀드·당사자·보수·환매 (종현)
│   └── shapes.ttl                               ✅  SHACL 규칙 (종현, 📝 보수 0~5% 제약 추가 W2)
│
├── docs/                                        ✅  문서 (살아있는 자산)
│   ├── PLAN.md                                  ✅  설계 — 무엇을·왜 (MVP)
│   ├── 실행계획.md                               ✅  실행 — 누가·언제 (4주 MVP)
│   ├── 역할분담.md                               ✅  ⭐ 역할·책임·RACI
│   ├── golden_master.md                         ✅  ⭐ 골든셋 스펙 (14컬럼·enum·κ 절차)
│   ├── tree.md                                  ✅  ⭐ 이 파일 — 디렉토리 한글 가이드
│   ├── ontology_pipeline.md                     ✅  파이프라인 현황 (종현)
│   ├── ontology_prd.md                          ✅  온톨로지 PRD (종현)
│   ├── EXTRACT_GUARD_PLAN.md                    ✅  ⭐ 추출·가드 설계 (PM 전담, Gemma 4)
│   └── INTERFACES.md                            ✅  ⭐ 단일 진실 스키마 (LLMBackend·Guard·score·manifest)
│
├── src/                                         ✅  소스 코드
│   ├── __init__.py                              ✅  패키지 표시
│   │
│   ├── client/                                  ✅  LLM SDK 래퍼
│   │   ├── anthropic_client.py                  ✅  Claude — caching·retry·usage 로깅 (종현)
│   │   └── ollama_client.py                     📝  Gemma 4 HTTP API + JSON Schema 강제 (승훈)
│   │
│   ├── schemas/                                 ✅  LLM 출력 강제 형식 (Pydantic)
│   │   └── extraction.py                        ✅  4개념 추출 스키마 (종현, 단일 소스)
│   │
│   ├── ingest/                                  📝  ⭐ PDF → 텍스트 (승훈)
│   │   └── pdf_to_text.py                       📝  스캔=Tesseract OCR / 디지털=pdfplumber, 페이지 보존
│   │
│   ├── extraction/                              📝  ⭐ 추출 백엔드 추상화 (승훈)
│   │   ├── backend_base.py                      📝  LLMBackend Protocol
│   │   ├── backend_ollama.py                    📝  Gemma 4 호출 + JSON Schema
│   │   ├── extractor.py                         📝  Doc-then-field 2-pass orchestration
│   │   └── prompts/
│   │       ├── extract_side_v1.md               📝  한 면 추출 프롬프트
│   │       └── retry_g1_v1.md                   📝  G1 형식 오류 재시도 프롬프트
│   │
│   ├── ontology/                                ✅  온톨로지 로딩·검증 래퍼
│   │   ├── mapping.py                           ✅  추출 JSON → ABox(개념 지도) 변환 (종현)
│   │   └── validate.py                          ✅  pyshacl 적정성 검증 래퍼 (종현)
│   │
│   ├── pipelines/                               ✅  태스크별 흐름
│   │   ├── extract.py                           ✅  추출 — Claude 경로 (종현)
│   │   ├── normalize.py                         ✅  단위·표기 정규화 (종현)
│   │   ├── cross_check.py                       ✅  교차검증 — 계약서값 vs IM값 (종현)
│   │   └── llm_judge.py                         ✅  의미 동등 판단 LLM 라우터 (종현)
│   │
│   ├── guards/                                  📝  ⭐ 가드 3종 — 출력 후처리 검증 (승훈)
│   │   ├── base.py                              📝  GuardEvent, GuardConfig, GuardContext, Guard Protocol
│   │   ├── g1_format.py                         📝  G1 형식 — Pydantic + 1회 재시도
│   │   ├── g2_citation.py                       📝  G2 출처 — pypdf 페이지 범위 확인
│   │   ├── g3_constraint.py                     📝  G3 제약 — 범위·논리 + SHACL 위임
│   │   └── registry.py                          📝  가드 ON/OFF 토글 + 체이닝
│   │
│   ├── scoring/                                 📝  ⭐ 채점·메트릭·비교 (승연) — LLM 호출 없음
│   │   ├── scorer.py                            📝  Accuracy·Precision·Recall·F1·환각률 코어
│   │   ├── breakdown.py                         📝  필드·난이도·변조·signal 세분화
│   │   └── compare.py                           📝  3개 score.json → compare.md
│   │
│   ├── cli/                                     📝  CLI 진입점 (건)
│   │   └── main.py                              📝  `dnb run / score / compare …` (typer)
│   │
│   └── stats/                                   📝  통계 검정 (승훈)
│       └── significance.py                      📝  McNemar + 부트스트랩 95% CI
│
├── prompts/                                     ✅  버전 관리되는 프롬프트
│   └── v0/
│       ├── extract/system.md                    ✅  4개념 추출 프롬프트 (종현)
│       ├── judge/system.md                      ✅  의미 동등 판단 프롬프트 (종현)
│       └── normalize/system.md                  ✅  정규화 프롬프트 (종현)
│
├── scripts/                                     ✅  일회성·실험용 (src 외부)
│   ├── hello_gemma.py                           ✅  Gemma 4 + JSON Schema smoke (승훈)
│   ├── run_extract_once.py                      ✅  단발 추출 PoC (종현)
│   ├── render_mermaid.py                        ✅  온톨로지 mermaid 렌더 (종현)
│   ├── render_ontology_graph.py                 ✅  온톨로지 그래프 렌더 (종현)
│   ├── render_figma_ontology_svg.py             ✅  Figma용 SVG 렌더 (종현)
│   ├── apply_perturbations.py                   📝  골든셋 변조 IM 값 적용 (건)
│   └── run_experiment.py                        📝  3조건(①②③) 전수 실행 (건)
│
├── tests/                                       ✅  pytest
│   ├── golden/                                  ✅  ⭐ 골든셋 (PLAN §6)
│   │   ├── golden_master.csv                    ✅  30문항 마스터 (정상18 + 변조12)
│   │   └── labeler_v1_rina.csv                  📝  리나 1차 라벨 (W1~W2)
│   ├── test_anthropic_client.py                 ✅  Anthropic SDK 래퍼
│   ├── test_extract_pipeline.py                 ✅  추출
│   ├── test_extraction_schema.py                ✅  Pydantic 스키마
│   ├── test_normalization.py                    ✅  정규화
│   ├── test_cross_check.py                      ✅  교차검증
│   ├── test_llm_judge.py                        ✅  LLM judge
│   ├── test_ontology_mapping.py                 ✅  JSON→ABox
│   ├── test_ontology_validate.py                ✅  SHACL
│   ├── test_run_extract_once.py                 ✅  PoC 스크립트
│   ├── test_render_mermaid.py                   ✅  렌더
│   ├── test_render_ontology_graph.py            ✅  렌더
│   ├── test_render_figma_ontology_svg.py        ✅  렌더
│   ├── test_scorer.py                           📝  채점기 단위 (승연)
│   ├── test_breakdown.py                        📝  세분화 (승연)
│   ├── test_compare.py                          📝  비교 리포트 (승연)
│   └── test_guards.py                           📝  가드 3종 (건)
│
└── reports/                                     🤖🚫  실행 결과 (자동 생성, gitignore)
    ├── manual_extract/                          ✅  종현 수동 PoC 결과 (참고용)
    └── <run_id>/                                🤖  예: exp_baseline_20260601_120000
        ├── manifest.json                        🤖  run 메타 (mode·model·seed·timestamps)
        ├── extraction.json                      🤖  4개념 추출 JSON
        ├── abox.ttl                             🤖  RDF/ABox
        ├── shacl_report.txt                     🤖  SHACL 검증 로그
        ├── cross_check.json                     🤖  교차검증 결과
        ├── guard_log.json                       🤖  가드 통과/거부 로그
        ├── score.json                           🤖  ⭐ 메트릭 12종 (승연)
        └── report.md                            🤖  단일 run 마크다운 리포트
```

---

## 2. 디렉토리별 한 줄 가이드 (헷갈리면 여기만)

| 디렉토리 | 역할 | 핵심 원칙 |
|----------|------|----------|
| `database/` | 펀드 PDF 원본 | **외부 업로드 절대 금지**. PDF는 gitignore |
| `ontology/` | 개념 지도(`.ttl`) + SHACL 규칙 | 개념·속성 이름의 **단일 소스**(종현). 바뀌면 공지 |
| `docs/` | 보고서·계획·역할·가이드·인터페이스 | PLAN/실행계획/역할분담/INTERFACES 변경 시 PR + 리뷰 |
| `src/client/` | LLM SDK 래퍼 (Claude·Gemma) | caching·retry·usage·timing 로깅 |
| `src/schemas/` | LLM 출력 강제 형식 (Pydantic) | 14필드 4개념 — 변경 금지 (단일 소스) |
| `src/ingest/` | PDF → 페이지별 텍스트 | 스캔=OCR / 디지털=pdfplumber. 페이지 번호 보존 |
| `src/extraction/` | LLM 추출 백엔드 + 2-pass orchestration | `LLMBackend` Protocol 통해 Claude·Gemma 교체 가능 |
| `src/ontology/` | JSON→ABox 변환·pyshacl 검증 래퍼 | 추출 결과를 개념 지도에 끼워 검사 |
| `src/pipelines/` | 정규화 → 교차검증 → judge 흐름 | 태스크 1개 = 파일 1개 |
| `src/guards/` | 가드 3종(형식·출처·제약) + Registry | 각 가드 = **순수함수**. **LLM 호출 금지** |
| `src/scoring/` | 채점기 — 출력 vs 골든셋·메트릭·비교 | **순수함수**(재현성). 통계 해석은 `src/stats/` |
| `src/stats/` | McNemar·부트스트랩 | 3조건 비교의 유의성 검정 |
| `src/cli/` | `dnb` 진입점 (typer) | run_id 부여·`reports/<run_id>/` 관리 |
| `prompts/` | 프롬프트 텍스트 (코드와 분리) | 호출에 `prompt_version` 기록 |
| `scripts/` | smoke·렌더·실험 실행 | 정식 모듈 아님 |
| `tests/golden/` | 골든셋 마스터 + 라벨링 시트 | PM 확정 freeze, 사양은 `docs/golden_master.md` |
| `tests/` | pytest | 채점기·가드·검증은 단위 테스트 필수 |
| `reports/` | 실행 결과 (자동·gitignore) | `<run_id>`별 raw 보존. `manual_extract/`만 git 추적 |

---

## 3. 누가 무엇을 가장 먼저 만드나 (W1)

| 담당 | 처음 만들 파일 | 목표 |
|------|--------------|------|
| **신승훈** (PM) | `docs/EXTRACT_GUARD_PLAN.md` + `docs/INTERFACES.md` (✅ 완료) + `scripts/hello_gemma.py` smoke (✅) + `src/ingest/pdf_to_text.py` + `src/client/ollama_client.py` | 추출·가드 백엔드 토대 + 인터페이스 freeze |
| **노종현** | (W1 거의 완료) `ontology/`·`src/pipelines/`·`prompts/v0/` 안정화 + W2 SHACL 보수 0~5% 제약 추가 | 추출·정규화·교차검증·Judge 안정 |
| **조건** | `src/cli/main.py` 골격(typer) + `scripts/apply_perturbations.py` 초안 | CLI 진입점 + 변조 적용 인프라 |
| **한승연** | `src/scoring/scorer.py`(Accuracy·Precision·Recall·F1·환각률) + `tests/test_scorer.py` | mock 데이터로 채점기 단위 테스트 통과 |
| **김리나** | `tests/golden/labeler_v1_rina.csv` 시작 (30개 PDF 대조 검수) | `docs/golden_master.md` 가이드 따라 라벨링 v1 |

---

## 4. .gitignore 에 들어가는 것 (절대 commit 금지)

```
database/**/*.pdf      # 펀드 원본
.env                   # API 키
reports/*/             # 실행 결과 (manual_extract/는 추적 유지)
__pycache__/
.pytest_cache/
*.pyc
.ipynb_checkpoints/
```

---

## 5. 이 트리는 어떻게 유지하나

- **신규 디렉토리·핵심 파일 추가 때마다** PR에서 이 파일도 함께 업데이트.
- "이거 어디 있어요?" 가 두 번 이상 나오면 → 트리에 누락된 것. 즉시 추가.
- 파일이 실제로 생기면 `📝` → `✅` 로 상태 갱신.
- 신규 합류자가 PLAN.md 다음으로 펴보는 문서 — 그 기준으로 가독성 유지.
