# R&R — 역할과 책임 (Roles & Responsibilities)

> 기준 문서: [`ROADMAP.md`](./ROADMAP.md) (MVP, 4주). 스코프가 바뀌면 이 문서도 갱신.
> 한 줄: **PM 1명(승훈) + 개발 3명(종현·건·승연) + 골든셋·발표 1명(리나). 골든셋 정답은 PM이 최종 확정.**
>
> 📖 **단어가 헷갈리면** [`ARCHITECTURE.md → 용어 사전`](./ARCHITECTURE.md) 참조 — 추출·가드·온톨로지·SHACL·cross_check·Judge·하네스·채점·골든셋의 정의를 한 표에서.

---

## 1. 팀원별 책임

### 신승훈 — PM · 추출(Gemma) · 가드 · 통계
- **책임**: 일정·통합 관리 / 골든셋 정답 **최종 확정**(κ 합의) / **Gemma 4 기반 추출 백엔드** (`src/ingest/`, `src/client/ollama_client.py`, `src/extraction/`) / **가드 3종** (G1 형식·G2 출처·G3 제약) / 통계(McNemar·부트스트랩) / 보고서 + 인터페이스 명세.
- **산출물**: `docs/reference/extract_guard_plan.md` + `docs/INTERFACES.md` / `tests/golden/golden_master.csv` PM 확정본 / `docs/GOLDENSET.md`(가이드) / `src/ingest/pdf_to_text.py` + `src/client/ollama_client.py` + `src/extraction/extractor.py` / `src/guards/{g1_format,g2_citation,g3_constraint,registry}.py` / `src/stats/significance.py`(McNemar·Bootstrap CI) / 학술제 보고서.
- **안 넘기는 선**: 골든셋 정답값은 PM이 확정(라벨러 의견 → 조정). 채점기·메트릭은 승연 영역(PM은 통계 검정·해석만). 가드는 **결정론 함수**(LLM 호출 금지). Gemma 호출 결정론(temp=0.1·seed=42·model hash 로깅).

### 노종현 — 온톨로지 · LLM 추출
- **책임**: 온톨로지(`trust_fund.ttl`·`shapes.ttl`) / 추출 프롬프트(tool-use) / JSON→ABox 변환 / 교차검증 로직 / 베이스라인(①) 모드.
- **산출물**: 온톨로지 2파일, 추출기, 교차검증, 그래프(W4).
- **안 넘기는 선**: 개념·속성 **이름의 단일 소스**. 변경 시 즉시 공지(가드·채점기가 깨짐).

### 조건 — CLI · 변조 · 실험 · 부트스트랩
- **책임**: `dnb` CLI 골격 + manifest 자동 생성 / 변조 적용 스크립트(골든셋 변조 12개 → IM 추출 결과 주입) / 3조건 전수 실행 러너 / 부트스트랩 신뢰구간.
- **산출물**: `src/cli/main.py` / `scripts/apply_perturbations.py` / `scripts/run_experiment.py` / 부트스트랩 결과.
- **안 넘기는 선**: 실험은 동일 입력·고정 seed. 추출·가드 모듈 내부 로직 수정 금지(승훈 영역) — 호출만.

### 한승연 — 검증 · 비교
- **책임**: 채점기(scorer) / 메트릭 계산(Accuracy·Precision·**Recall ★**·F1·환각률) / 세분화 분석(필드·난이도·변조유형·harness_signal별) / 3조건 비교 리포트(`compare.md`).
- **산출물**: `src/scoring/scorer.py`, `reports/<run_id>/score.json`, `reports/compare_*.md`.
- **안 넘기는 선**: 채점기 안에 **LLM 호출 금지**(순수함수). 골든셋 정답값 임의 변경 금지. 숫자 임의 반올림·필터 금지 — 통계 검정·해석은 PM 영역.

### 김리나 — 골든셋 검수 · 발표
- **책임**: `tests/golden/golden_master.csv` 30개 PDF 대조 검수(라벨러) / 변조 케이스 검수 / κ 합의 / 발표 장표·대본. 가이드: `docs/GOLDENSET.md`.
- **산출물**: `tests/golden/labeler_v1_rina.csv`, 변조 검수 메모, 발표자료.
- **안 넘기는 선**: 코드 수정 금지. `contract_raw` 변경 금지. 합성 케이스(C002·C014·C029) 손대지 말 것. 추측 라벨 금지(모르면 `note` + PM 질문).

---

## 2. RACI 표

> **R**=실행 · **A**=최종책임(1명) · **C**=협의 · **I**=공유

| 산출물 / 활동 | 승훈 | 종현 | 건 | 승연 | 리나 |
|---------------|:---:|:---:|:---:|:---:|:---:|
| 온톨로지(ttl·shapes) | C | **A/R** | I | I | I |
| LLM 추출 (Claude 백엔드) | I | **A/R** | I | C | I |
| LLM 추출 (Gemma 백엔드) | **A/R** | C | I | C | I |
| 교차검증·Judge 로직 | C | **A/R** | I | C | I |
| 가드 3종 (G1·G2·G3) | **A/R** | C | I | I | I |
| 파이프라인·CLI | C | C | **A/R** | I | I |
| 골든셋 검수·라벨링 | **A** | I | C | I | **R** |
| 변조 케이스 작성·검수 | A | I | C(적용) | I | **R** |
| 채점기·메트릭·비교 리포트 | C | C | I | **A/R** | I |
| 3조건 실험 실행 | A | C | **R** | C | I |
| 통계(McNemar·부트스트랩) | **A/R** | I | R | I | I |
| 발표 장표·보고서 | A(보고서) | C | C | C | **R**(장표) |
| 일정·통합 | **A/R** | I | I | I | I |

---

## 3. 협업 규칙 (최소)

- **(1) `main` 직접 push 금지** — 브랜치 → PR → 리뷰 1명 → 머지.
- **(2) 막히면 24시간 안에 PM 호출** — 혼자 끌어안지 않기.
- **인터페이스 먼저** — 추출 출력 형식 / 가드 결과 형식 / 골든셋 형식을 W1에 합의·고정한 뒤 병렬 작업.
- **보안** — `database/*.pdf`·`.env`는 커밋·외부 업로드 금지.

---

## 4. 두 개의 관문 (늦으면 전체 지연)

1. **W1 — 인터페이스 형식 합의** (추출·가드·골든셋)
2. **W2 끝 — 골든셋 30 freeze + κ ≥ 0.7**
