# 📂 프로젝트 디렉토리 트리 (한글 주석)

> 한양대 D&B 학술제 7팀 · DnB Harness · 최종 갱신 2026-05-27 (**MVP 스코프**)
> 설계 [`PLAN.md`](./PLAN.md) + 실행 [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md) 기준.
> 각 파일 옆 표시 — `✅` 이미 있음 / `📝` 곧 만들 것 / `🚫` git 제외 / `🤖` 자동 생성

---

## 1. 전체 트리

```
DnB_harness/
│
├── .gitignore                                   ✅  PDF·.env·reports/ 등 제외 룰
├── LICENSE                                      ✅  라이선스
├── README.md                                    ✅  프로젝트 한 줄 소개
├── requirements.txt                             ✅  의존성 (📝 rdflib·pyshacl·statsmodels 추가 필요)
├── .env                                         🚫  ANTHROPIC_API_KEY (각자 작성, gitignore)
├── .env.example                                 📝  키 템플릿 (승훈)
│
├── database/                                    ✅  펀드 PDF + 골든셋 (🚫 외부 공유 금지)
│   ├── 이지스 블랙ON 1호_준감필.pdf              ✅  투자제안서(IM) — 디지털 PDF
│   ├── 핵심상품설명서_…_준감필.pdf               ✅  핵심상품설명서 — 디지털 PDF
│   ├── 제정신탁계약서_날인본_…_최종버전.pdf       ✅  신탁계약서 — 스캔 이미지 PDF (교차검증 기준)
│   └── labels/igis_blackon_1/                   📝  골든셋 (W1~)
│       ├── golden_master.csv                    📝  ⭐ 30문항 마스터 시트 (리나 라벨 → 승훈 확정)
│       └── perturbations.csv                    📝  변조 12문항 명세: 무엇을 어떻게 (리나 작성)
│
├── ontology/                                    📝  ⭐ 온톨로지 (rdflib + pyshacl) — 신규
│   ├── trust_fund.ttl                           📝  코어 4개념 정의: 펀드·당사자·보수·환매 (종현)
│   └── shapes.ttl                               📝  SHACL 규칙: 보수 0~5%·만기>설정일 등 (종현)
│
├── docs/                                        ✅  문서 (살아있는 자산)
│   ├── REPORT.md                                ✅  상사 보고용 보고서
│   ├── PLAN.md                                  ✅  설계 — 무엇을·왜 (MVP)
│   ├── 실행계획.md                               ✅  실행 — 누가·언제 (4주 MVP)
│   ├── tree.md                                  ✅  ⭐ 이 파일 — 디렉토리 한글 가이드
│   ├── labeling_guide.md                        📝  라벨링 가이드·모호 케이스 (승훈, W1)
│   └── onboarding/                              ✅  멤버별 시작 가이드
│       ├── README.md                            ✅  공통 셋업 + 운영 룰 + 용어사전
│       ├── R&R.md                               ✅  역할·RACI (MVP 반영)
│       ├── 01_lead_harness.md                   ✅  신승훈 (📝 MVP로 갱신 예정)
│       ├── 02_agent_prompt.md                   ✅  노종현 (📝 갱신 예정)
│       ├── 03_guards.md                         ✅  조건   (📝 갱신 예정)
│       ├── 04_pipeline.md                       ✅  한승연 (📝 갱신 예정)
│       └── 05_docs.md                           ✅  김리나 (📝 갱신 예정)
│
├── src/                                         📝  소스 코드 (W1~ 점진 추가)
│   ├── __init__.py                              📝  패키지 표시
│   ├── cli.py                                   📝  typer 진입점 `python -m src.cli …` (승연)
│   │
│   ├── client/                                  📝  Anthropic SDK 래퍼
│   │   └── anthropic_client.py                  📝  caching·retry·usage 로깅 (건)
│   │
│   ├── schemas/                                 📝  LLM 출력 강제 형식 (Pydantic)
│   │   └── extraction.py                        📝  4개념 추출 스키마 (종현)
│   │
│   ├── ontology/                                📝  온톨로지 로딩·검증 래퍼
│   │   ├── mapping.py                           📝  추출 JSON → ABox(개념 지도) 변환 (종현)
│   │   └── validate.py                          📝  pyshacl 적정성 검증 래퍼 (종현)
│   │
│   ├── pipelines/                               📝  태스크별 흐름
│   │   ├── extract.py                           📝  추출 — tool-use 구조화 출력 (종현)
│   │   ├── cross_check.py                       📝  교차검증 — 계약서값 vs IM값 (종현)
│   │   └── reporter.py                          📝  리포트 markdown 자동 생성 (승연)
│   │
│   ├── guards/                                  📝  가드 3종 — 출력 후처리 검증
│   │   ├── registry.py                          📝  가드 ON/OFF 토글 (건)
│   │   ├── schema_guard.py                      📝  G1 형식 — 빈칸 형식 검증 (건)
│   │   ├── citation_guard.py                    📝  G2 출처 — 없는 페이지 인용 차단 (건)
│   │   └── constraint_guard.py                  📝  G3 제약 — 범위·논리 위반 차단 (건)
│   │
│   ├── eval/                                    📝  채점 (LLM 호출 없는 순수 함수)
│   │   └── consistency_scorer.py                📝  불일치 탐지 Precision/Recall/F1 (승훈)
│   │
│   └── stats/                                   📝  통계 검정
│       └── significance.py                      📝  McNemar + 부트스트랩 CI (승훈/건)
│
├── prompts/                                     📝  버전 관리되는 프롬프트
│   └── v0/
│       ├── extract/system.md                    📝  4개념 추출 프롬프트 (종현)
│       └── baseline/system.md                   📝  ① 베이스라인 — 자유 질의 (종현)
│
├── scripts/                                     📝  일회성·실험용 (src 외부)
│   ├── hello_claude.py                          📝  API 연결 smoke (공통, W1)
│   ├── build_golden.py                          📝  golden_master.csv → 채점용 파일 변환 (승연)
│   ├── apply_perturbations.py                   📝  IM 값 변조 적용 (건)
│   └── run_experiment.py                        📝  3조건(①②③) 전수 실행 (건)
│
├── tests/                                       📝  pytest
│   ├── test_consistency_scorer.py               📝  채점기 정합성 (승훈)
│   ├── test_guards.py                           📝  가드 3종 (건)
│   └── test_validate.py                         📝  SHACL 검증 (종현)
│
└── reports/                                     🤖🚫  실행 결과 (자동 생성, gitignore)
    ├── .gitkeep                                 📝  디렉토리만 git에 남김 (승연)
    └── <run_id>/                                🤖  예: run_20260527_153012_a1b2
        ├── report.md                            🤖  메트릭·표·결론
        ├── results.json                         🤖  3조건 결과 (재채점용)
        └── figures/                             🤖  F1 막대 등 (matplotlib)
```

---

## 2. 디렉토리별 한 줄 가이드 (헷갈리면 여기만)

| 디렉토리 | 역할 | 핵심 원칙 |
|----------|------|----------|
| `database/` | 펀드 PDF + 사람이 라벨한 골든셋 30문항 | **외부 업로드 절대 금지**. PDF는 gitignore |
| `ontology/` | 개념 지도(`.ttl`) + SHACL 규칙 | 개념·속성 이름의 **단일 소스**(종현). 바뀌면 공지 |
| `docs/` | 보고서·계획·역할·가이드 | PLAN/EXECUTION 변경 시 PR + 리뷰 |
| `docs/onboarding/` | 멤버별 가이드 + R&R | 신규 합류자가 먼저 펴보는 곳 |
| `src/schemas/` | LLM 출력 강제 형식 (Pydantic) | W1에 형식 합의 → 고정 |
| `src/ontology/` | JSON→ABox 변환·pyshacl 검증 래퍼 | 추출 결과를 개념 지도에 끼워 검사 |
| `src/pipelines/` | 추출 → 교차검증 → 리포트 흐름 | 태스크 1개 = 파일 1개 |
| `src/guards/` | 가드 3종(형식·출처·제약) | 각 가드 = `check(...) -> GuardResult`. **LLM 호출 금지** |
| `src/eval/` | 채점기 — 출력 vs 골든셋 | **순수 함수**(재현성) |
| `src/stats/` | McNemar·부트스트랩 | 3조건 비교의 유의성 검정 |
| `prompts/` | 프롬프트 텍스트 (코드와 분리) | 호출에 `prompt_version` 기록 |
| `scripts/` | smoke·골든셋 빌드·변조·실험 실행 | 정식 모듈 아님 |
| `tests/` | pytest | 채점기·가드·검증은 단위 테스트 필수 |
| `reports/` | 실행 결과 (자동·gitignore) | `<run_id>`별 raw 보존 |

---

## 3. 누가 무엇을 가장 먼저 만드나 (W1)

| 담당 | 처음 만들 파일 | 목표 |
|------|--------------|------|
| **신승훈** | `database/labels/igis_blackon_1/golden_master.csv`(양식) + `docs/labeling_guide.md` + `src/eval/consistency_scorer.py` | 골든셋 양식 + 채점기 |
| **노종현** | `ontology/trust_fund.ttl`(4개념) + `prompts/v0/extract/system.md` + `src/pipelines/extract.py` | 개념 지도 + 추출 JSON |
| **조건** | `src/client/anthropic_client.py` + `src/guards/citation_guard.py` | AI 호출 공용 함수 + 출처 가드 |
| **한승연** | `src/cli.py` + `src/__init__.py` + `scripts/hello_claude.py` | `python -m src.cli` 한 줄 동작 |
| **김리나** | `golden_master.csv` 정상값 라벨링 시작 | PDF 정독 + 정답 채우기 |

---

## 4. .gitignore 에 들어가는 것 (절대 commit 금지)

```
database/**/*.pdf      # 펀드 원본
.env                   # API 키
reports/*/             # 실행 결과 (.gitkeep만 유지)
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
