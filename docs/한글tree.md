# 📂 프로젝트 디렉토리 트리 (한글 주석)

> 한양대 D&B 학술제 7팀 · DnB Harness · 최종 갱신 2026-05-24
> [PLAN.md §6 아키텍처](./PLAN.md) + [onboarding/](./onboarding/) 의 모든 산출물을 한 곳에.
> 각 파일 옆 표시 — `✅` 이미 있음 / `📝` 곧 만들 것 / `🚫` git 제외 / `🤖` 자동 생성

---

## 1. 전체 트리

```
DnB_harness/
│
├── .git/                                        ✅  Git 저장소 (자동)
├── .gitignore                                   ✅  PDF·.env·reports/·__pycache__ 등 제외 룰
├── LICENSE                                      ✅  라이선스
├── README.md                                    ✅  프로젝트 한 줄 소개 (📝 보강 예정)
├── requirements.txt                             ✅  파이썬 의존성 (Phase 0)
├── .env                                         🚫  ANTHROPIC_API_KEY (각자 작성, gitignore)
├── .env.example                                 📝  키 템플릿 (Phase 0, 승훈)
│
├── database/                                    ✅  펀드 PDF + 라벨 (🚫 외부 공유 금지)
│   ├── 이지스 블랙ON 1호_준감필.pdf              ✅  핵심 사모펀드 자료 (텍스트 PDF)
│   ├── 핵심상품설명서_이지스블랙ON일반사모투자신탁제1호_준감필.pdf   ✅  핵심상품설명서 (텍스트 PDF)
│   ├── 제정신탁계약서_날인본_이지스블랙ON1호_20250722_최종버전.pdf  ✅  신탁계약서 (스캔 이미지 PDF)
│   └── labels/                                  📝  골든셋 라벨 (1주차~)
│       └── igis_blackon_1/
│           ├── anchors.yaml                     📝  앵커 사실 25~35개 (승훈+조건, 1~2주차)
│           └── risks.yaml                       📝  리스크 체크리스트 정답 (조건, Phase 1)
│
├── docs/                                        ✅  문서 (살아있는 자산)
│   ├── PLAN.md                                  ✅  프로젝트 계획서 (single source of truth)
│   ├── R&R.md                                   ✅  멤버별 역할·RACI
│   ├── 한글tree.md                              ✅  ⭐ 이 파일 — 디렉토리 한글 가이드
│   ├── guards.md                                📝  가드 5종 명세 (조건, 1주차)
│   ├── labeling_guide.md                        📝  라벨링 가이드·모호 케이스 (승훈+조건+리나, 2주차)
│   ├── related-work.md                          📝  선행 연구 3~5건 (리나, 1주차)
│   ├── glossary.md                              📝  펀드·LLM 용어사전 (리나, 1주차)
│   ├── presentation_outline.md                  📝  학술제 발표 12장 골격 (리나, 2주차)
│   └── onboarding/                              ✅  멤버별 시작 가이드 — 신규 합류자가 1주차부터 따라갈 자료
│       ├── README.md                            ✅  공통 셋업 + 운영 룰 + 용어사전
│       ├── 01_lead_harness.md                   ✅  신승훈 — PM·코어·골든셋
│       ├── 02_agent_prompt.md                   ✅  노종현 — 프롬프트·스키마
│       ├── 03_guards.md                         ✅  조건 — 가드·Ablation
│       ├── 04_pipeline.md                       ✅  한승연 — CLI·리포트
│       └── 05_docs.md                           ✅  김리나 — 문서·리뷰·발표
│
├── src/                                         📝  소스 코드 (Phase 0~3 점진 추가)
│   ├── __init__.py                              📝  패키지 표시 (Phase 0)
│   ├── cli.py                                   📝  typer 진입점 — `python -m src.cli ...` (승연, 1주차)
│   │
│   ├── client/                                  📝  Anthropic SDK 래퍼
│   │   ├── __init__.py
│   │   └── anthropic_client.py                  📝  HarnessClient: caching·retry·usage 로깅 (승훈, 2주차)
│   │
│   ├── schemas/                                 📝  Pydantic 모델 — 모든 LLM 출력의 강제 형식
│   │   ├── __init__.py
│   │   ├── anchor_extraction.py                 📝  ExtractedAnchor·Source·ExtractAnchorsOutput (종현, 1주차)
│   │   ├── consistency.py                       📝  Discrepancy·ConsistencyReport (종현, 2주차)
│   │   └── risk_assessment.py                   📝  RiskItem·RiskAssessment (종현, Phase 1)
│   │
│   ├── pipelines/                               📝  태스크별 LLM 호출 파이프라인
│   │   ├── __init__.py
│   │   ├── extract_anchors_v0.py                📝  앵커 추출 — system prompt + tool-use (종현, 1주차)
│   │   ├── check_consistency_v0.py              📝  3종 문서 일관성 검증 (종현, 2주차)
│   │   ├── risk_checklist_v0.py                 📝  리스크 체크리스트 매핑 (종현, Phase 1)
│   │   └── reporter.py                          📝  리포트 markdown 자동 생성 (승연, 2주차)
│   │
│   ├── eval/                                    📝  채점 (LLM 호출 없는 순수 함수)
│   │   ├── __init__.py
│   │   ├── anchor_scorer.py                     📝  Exact Match·F1 (승훈, 1주차)
│   │   ├── consistency_scorer.py                📝  Detection P/R/F1·FAR (승훈, Phase 2)
│   │   └── risk_scorer.py                       📝  항목별 P/R·Cohen's κ (승훈, Phase 1)
│   │
│   ├── guards/                                  📝  가드 5종 — 출력 후처리 검증
│   │   ├── __init__.py
│   │   ├── registry.py                          📝  가드 ON/OFF 토글 매니저 (조건, 2주차)
│   │   ├── schema_guard.py                      📝  G1 — Pydantic 스키마 검증 (조건, 2주차)
│   │   ├── citation_guard.py                    📝  G2 — doc/page 실재 여부 (조건, 1주차)
│   │   ├── range_guard.py                       📝  G3 — 숫자 도메인 범위 (조건, 2주차)
│   │   ├── cross_doc_guard.py                   📝  G4 — 3종 문서 값 일치 (조건, 2주차)
│   │   └── severity_guard.py                    📝  G5 — severity 룰북 보정 (조건, 2주차)
│   │
│   └── perturb/                                 📝  PDF 변조 생성기 (Phase 2)
│       ├── __init__.py
│       ├── pdf_perturb.py                       📝  pymupdf로 텍스트 redaction + overlay (승훈, Phase 2)
│       └── perturb_specs.yaml                   📝  변조 카테고리·대상 필드 명세 (Phase 2)
│
├── prompts/                                     📝  버전 관리되는 프롬프트
│   └── v0/                                      📝  첫 버전 (이후 v0_b, v1 분기)
│       ├── extract_anchors/
│       │   ├── system.md                        📝  앵커 추출 system prompt (종현, 1주차)
│       │   └── few_shot.md                      📝  Few-shot 예시 (선택)
│       ├── check_consistency/
│       │   └── system.md                        📝  일관성 검증 (종현, 2주차)
│       └── risk_checklist/
│           └── system.md                        📝  리스크 체크 (Phase 1)
│
├── scripts/                                     📝  일회성·개발용 스크립트 (`src/` 외부)
│   ├── hello_claude.py                          📝  API 연결 smoke test (공통, 0주차)
│   ├── hello_typer.py                           📝  CLI 학습용 (승연, 0주차)
│   ├── try_extract.py                           📝  추출 동작 확인 (종현, 1주차)
│   └── run_ablation.py                          📝  가드 ablation 실험 (조건, 2주차)
│
├── tests/                                       📝  pytest 단위·통합 테스트
│   ├── __init__.py
│   ├── test_anchor_scorer.py                    📝  scorer 채점 정합성 (승훈, 1주차)
│   ├── test_schemas.py                          📝  Pydantic 스키마 (종현, 1주차)
│   └── guards/
│       ├── __init__.py
│       └── test_citation_guard.py               📝  가드 단위 테스트 (조건, 1주차)
│
└── reports/                                     🤖🚫  실행 결과 (자동 생성, gitignore)
    ├── .gitkeep                                 📝  디렉토리만 git에 남김 (승연, 1주차)
    └── <run_id>/                                🤖  예: run_20260524_153012_a1b2
        ├── report.md                            🤖  메트릭·표·결론 (승연 reporter가 생성)
        ├── meta.json                            🤖  run_id·prompt_version·schema_version·model
        ├── raw/                                 🤖  LLM 원본 응답 (사후 재채점용)
        │   └── <task>_<idx>.json
        └── figures/                             🤖  ablation 그래프 등 (matplotlib 저장)
```

---

## 2. 디렉토리별 한 줄 가이드 (헷갈리면 여기만 보면 됨)

| 디렉토리 | 역할 | 핵심 원칙 |
|----------|------|----------|
| `database/` | 펀드 원본 PDF + 사람이 라벨한 골든셋 | **외부 업로드 절대 금지** (NDA). PDF는 gitignore |
| `docs/` | 살아있는 문서 — 계획·역할·가이드·발표 | PLAN/R&R은 변경 시 PR + 리뷰 |
| `docs/onboarding/` | 멤버별 1~2주차 단계별 가이드 | 신규 합류자가 가장 먼저 펴보는 곳 |
| `src/` | 실제 운영되는 소스 코드 (PR 필수) | 모듈 분리 + 순수 함수 우선 |
| `src/schemas/` | LLM 출력의 강제 형식 (Pydantic) | 종현↔조건↔승훈 3자 합의 → 버전 관리 |
| `src/client/` | Anthropic SDK 래퍼 (caching·retry) | 모든 호출은 반드시 이 래퍼를 거침 |
| `src/pipelines/` | "PDF → 프롬프트 → LLM → JSON" 흐름 | 태스크 1개 = 파일 1개 |
| `src/eval/` | 채점기 — LLM 출력과 골든셋 비교 | **순수 함수** (LLM 호출 금지, 재현성) |
| `src/guards/` | 가드 5종 (출력 후처리 검증) | 각 가드 = `check(...) -> GuardResult` 같은 인터페이스 |
| `src/perturb/` | 변조 PDF 생성 (의도적 모순 주입) | Phase 2에서 본격화 |
| `prompts/` | 프롬프트 텍스트 (코드와 분리) | 모든 호출에 `prompt_version` 기록 |
| `scripts/` | 일회성·실험·smoke 스크립트 | `src/` 와 달리 정식 모듈 아님 |
| `tests/` | pytest | scorer·스키마·가드는 단위 테스트 필수 |
| `reports/` | 실행 결과 (자동 생성·gitignore) | `<run_id>` 별로 raw 응답까지 보존 |

---

## 3. 누가 무엇을 가장 먼저 만드나 (1주차)

| 담당 | 처음 만들 파일 | 목표 |
|------|--------------|------|
| **신승훈** | `database/labels/igis_blackon_1/anchors.yaml` (10건) + `src/eval/anchor_scorer.py` + `tests/test_anchor_scorer.py` | 골든셋 시작 + 채점기 동작 |
| **노종현** | `prompts/v0/extract_anchors/system.md` + `src/schemas/anchor_extraction.py` + `src/pipelines/extract_anchors_v0.py` + `scripts/try_extract.py` | tool-use로 안정적 JSON 출력 1태스크 |
| **조건** | `docs/guards.md` (5종 명세) + `src/guards/citation_guard.py` + `tests/guards/test_citation_guard.py` | 가드 1개 동작 + 5종 설계 완료 |
| **한승연** | `src/cli.py` + `src/__init__.py` + `scripts/hello_typer.py` | `python -m src.cli smoke --fund ...` 동작 |
| **김리나** | `docs/related-work.md` (3~5건) + `docs/glossary.md` (10~15개) | 선행 연구 + 용어 정리 |

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

- **신규 디렉토리·핵심 파일이 추가될 때마다** PR에서 이 파일도 함께 업데이트.
- "이거 어디에 있어요?" 가 슬랙에 두 번 이상 올라오면 → 그 항목이 이 트리에 누락된 것. 즉시 추가.
- Phase 종료 시 `📝` → `✅` 로 상태 갱신.
- 이 파일은 **신규 합류자가 PLAN.md 다음으로 펴보는 문서**여야 한다 — 그 기준으로 가독성 유지.
