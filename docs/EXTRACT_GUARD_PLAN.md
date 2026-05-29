# 추출·가드 설계 — Gemma 4 로컬 백엔드 (PM 전담)

> 추출(Extract)과 가드(Guard) 레이어를 로컬 Gemma 4 기반으로 PM(승훈)이 전담 구현하는 설계서.
> 기준: [`PLAN.md §3·§4`](./PLAN.md), [`golden_master.md`](./golden_master.md), [`INTERFACES.md`](./INTERFACES.md).
> 최종 갱신: 2026-05-29.

---

## 0. 핵심 결정 한 줄

**Ollama + Gemma 4 31B (JSON Schema 강제) + OCR/pdfplumber 입력 + G1·G2·G3 가드 순수 코드**. 7개 모듈로 분할, 새 코드 ~800줄, 종현의 기존 Claude 경로와 병렬 공존.

### 검증된 사실 (2026-05-29 smoke 통과)

| 항목 | 결과 |
|---|---|
| Ollama 0.24.0 + `gemma4:31b` (Q4_K_M) | ✅ 동작 |
| 모델 capabilities | `completion + vision + tools + thinking` |
| 컨텍스트 길이 | **262,144** (62 페이지 PDF 텍스트 전부 + 프롬프트 여유) |
| JSON Schema 강제 (`format` 인자) | ✅ valid JSON 반환 |
| 한국어 추출 정확도 (펀드명, 보수율) | ✅ raw_text 그대로 + page 정확 |
| 결정론 (seed=42, temp=0.1) | ✅ 두 번 호출 결과 동일 |
| 환각 (본문에 없는 값) | ✅ null 반환 (환각 X) |
| 응답 속도 | 0.5~2.6초 / 필드 |

→ smoke 스크립트: [`scripts/hello_gemma.py`](../scripts/hello_gemma.py)

---

## 1. 5개 레이어 (PM 책임 범위)

```
PDF 2개
  │
  ▼
┌─────────────────────────────────────────────┐
│ 1. ingest/pdf_to_text.py                    │  스캔 계약서 → Tesseract OCR
│    페이지별 텍스트 + 페이지 번호 보존       │  디지털 IM     → pdfplumber
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ 2. client/ollama_client.py                  │  Ollama HTTP API 래퍼
│    + JSON Schema 강제 + 시드·온도 통일      │  retry, usage, timing 로깅
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ 3. extraction/extractor.py                  │  14필드 추출 오케스트레이션
│    Doc-then-field 2-pass 전략               │  ExtractionResult 반환
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ 4. guards/g1_format.py                      │  Pydantic + 1회 재시도
│    JSON 스키마 위반 → 재요청 + 실패 reject  │
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ 5. guards/g2_citation.py                    │  pypdf 페이지 범위 확인
│    page > N or page < 1 → 그 필드 null      │
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ 6. guards/g3_constraint.py                  │  결정론 범위/논리 검사
│    보수 0~5%, 만기>설정일, bool 패턴 등     │  + SHACL 호출(선택)
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ 7. guards/registry.py                       │  ON/OFF 토글, 가드 체이닝
│    GuardEvent 누적 → guard_log.json         │
└─────────────────────────────────────────────┘
```

→ **종현의 [`src/pipelines/extract.py`](../src/pipelines/extract.py)(Claude) 는 그대로**. 둘 다 같은 [`ExtractionResult`](../src/schemas/extraction.py) 출력 → 가드·이후 단계 공통.

---

## 2. 로컬 LLM 스택 결정 (Ollama)

| 옵션 | 추천도 | 결정 근거 |
|---|---|---|
| **Ollama 0.24+** | ★★★★★ | JSON Schema 강제 네이티브 / HTTP API / 모델 hash 노출(재현성) / 이미 동작 확인 |
| llama.cpp | ★★★ | 직접 제어 가능하나 API 자작 필요 |
| LM Studio | ★★ | GUI 친화, 자동화 불편 |
| vLLM | ★ | VRAM 많이 먹음, 셋업 복잡 |

### Gemma 4 31B 선택 이유
- 32B급 파라미터 → 한국어 추출 정확도 충분
- 262K 컨텍스트 → 두 PDF + 14필드 한 번에 처리 가능
- vision + tools + thinking 지원 → 향후 확장 옵션
- Q4_K_M 양자화 → 19GB VRAM 적합
- smoke 테스트 4/4 통과

### 비교 백엔드 (시간 남으면)
| 모델 | 파라미터 | 한국어 | 용도 |
|---|---|---|---|
| `gemma4:31b` | 31.3B | 강 | **MVP 기본** ★ |
| `qwen3.5:27b` | 27B | 매우 강 | 한국어 강점 백엔드 비교 |
| `gemma4:4b` | (옵션) | 약 | "약할수록 효과 큼" 시연 |

---

## 3. 입력 파이프라인 (PDF → 텍스트 OR 이미지)

**구현 결정**: PDF 종류에 따라 자동 분기.

| PDF 종류 | 처리 | 페이지 번호 보존 |
|---|---|---|
| **디지털 IM** | pdfplumber → 페이지별 텍스트 | ✅ 자동 |
| **스캔 계약서** | pdf2image → 페이지별 base64 PNG → **Gemma 4 vision 입력** | ✅ 이미지 순서로 |

> 원래 plan 은 Tesseract Korean OCR 였지만, Tesseract 시스템 설치 부담 + Gemma 4 vision 가용성 → vision 모드로 단순화 (2026-05-29 결정).

### 자동 분기 (`_is_scanned`)
- 첫 3 페이지의 임베디드 텍스트 < 50자 → 스캔본 (vision)
- 그 이상 → 디지털 (텍스트)

### Poppler 자동 탐색
Conda env 의 `Library/bin/pdfinfo.exe` 자동 검색 → `convert_from_path(poppler_path=...)` 로 전달. 시스템 PATH 의존 제거.

### 모듈 시그니처 [`src/ingest/pdf_to_text.py`](../src/ingest/pdf_to_text.py)

```python
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class PageText:
    page: int            # 1-based, PDF 뷰어 기준
    text: str            # 정규화된 텍스트
    source: str          # "ocr" | "embedded"

@dataclass(frozen=True)
class DocumentText:
    pdf_path: Path
    pdf_sha256: str      # 재현성 키
    pages: list[PageText]
    
    def total_pages(self) -> int: ...
    def text_for_extract(self, max_chars_per_page: int = 4000) -> str:
        """[Page N]\\n<text>\\n 형식으로 결합."""
```

### 자동 분기
- 첫 5페이지의 임베디드 텍스트가 임계치(예: 200자) 미만 → 스캔본 → Tesseract
- 그 외 → 디지털 → pdfplumber

### 시스템 의존성
| 도구 | 용도 | 설치 |
|---|---|---|
| Tesseract 5+ + `kor.traineddata` | OCR | `winget install UB-Mannheim.TesseractOCR` |
| Poppler | pdf2image 백엔드 | `conda install -c conda-forge poppler` |
| pdfplumber | 디지털 PDF | pip (requirements.txt 추가) |
| pytesseract | Tesseract Python 바인딩 | pip (requirements.txt 추가) |

---

## 4. 추출 형식 (Gemma 4 호출)

### 4.1 전략: Doc-then-side 2-pass

| Pass | 입력 | 스키마 | 출력 |
|---|---|---|---|
| 1 | 계약서 **이미지** (vision) 또는 텍스트 | `SideExtraction` | 14필드 contract 측 |
| 2 | IM **텍스트** (pdfplumber) | `SideExtraction` | 14필드 IM 측 |
| Merge | 1·2 결과 zip | — | `ExtractionResult` 생성 |

> 262K 컨텍스트라 단일 패스도 가능하나, 2-pass 가 안정·디버깅 용이. Pass 별 schema 가 작아 JSON Schema 강제도 빠름.

### 4.1.1 `SideExtraction` 스키마 (신규)

**위치**: [`src/extraction/side_schemas.py`](../src/extraction/side_schemas.py)

`ExtractionResult` 는 `ComparableField(contract, im)` 으로 양쪽을 한 객체에 묶지만, 한 번 호출에 한 면만 처리하려면 *평탄한* 스키마가 필요. → `FundSide` · `PartySide` · `FeeScheduleSide` · `RedemptionTermsSide` 정의 + `SideExtraction` 번들 + `merge_sides(contract_side, im_side) → ExtractionResult` 합성 함수.

```python
class FundSide(StrictSideModel):
    name: DocumentValue
    type: DocumentValue
    inception_date: DocumentValue
    maturity_date: DocumentValue

class SideExtraction(StrictSideModel):
    fund: FundSide
    party: PartySide
    fee_schedule: FeeScheduleSide
    redemption_terms: RedemptionTermsSide

def merge_sides(contract_side, im_side) -> ExtractionResult:
    """각 필드를 ComparableField(contract=..., im=...) 로 묶어 합성."""
    ...
```

→ Ollama JSON Schema 호출 시 `SideExtraction.model_json_schema()` 를 grammar 로 사용. ExtractionResult 의 절반 크기라 추론 안정·빠름.

### 4.2 Ollama JSON Schema 호출 (smoke 검증된 형태)

```python
import requests
from src.schemas.extraction import FundExtraction  # 한 면(side) 스키마

schema = FundExtraction.model_json_schema()  # Pydantic v2 → JSON Schema

response = requests.post("http://localhost:11434/api/generate", json={
    "model": "gemma4:31b",
    "prompt": prompt,
    "format": schema,             # Ollama가 grammar 토큰 수준에서 강제
    "stream": False,
    "options": {
        "temperature": 0.1,       # 0이 아닌 0.1: Q4 양자화 degenerate 회피
        "seed": 42,
        "num_predict": 4096,
    }
})
raw = response.json()["response"]
extraction = FundExtraction.model_validate_json(raw)
```

> **smoke 결과**: temp=0.1 + seed=42 → 두 번 호출 결과 동일 (결정론 확인). temp=0은 한국어 텍스트에서 token 반복 폭주 가능성.

### 4.3 프롬프트 (한국어, side-aware)

**위치**: [`src/extraction/extractor.py`](../src/extraction/extractor.py) 내 `SYSTEM_RULES` 상수.

> 원래 plan 은 `prompts/extract_side_v1.md` 외부 파일이었으나 MVP 가속을 위해 인라인 결정 (2026-05-29). 프롬프트 버전 관리가 필요해지면 그때 분리.

프롬프트는 `{doc_role}` placeholder (= `"신탁계약서"` 또는 `"IM"`) 를 가짐 → pass 별로 format 해 호출.

```markdown
당신은 한국 사모펀드 신탁계약서·투자제안서 검토 전문가입니다.

아래 문서에서 4개념 × 다음 필드를 정확히 추출하세요:

| 개념 | 필드 |
|---|---|
| fund | name, type, inception_date, maturity_date |
| party | asset_manager, trustee, distributor |
| fee_schedule | management_fee, trust_fee, sales_fee |
| redemption_terms | is_redeemable, lockup_period, redemption_cycle, redemption_fee |

규칙:
1. raw_text는 PDF 원문 그대로 (요약·바꿔 쓰기 금지).
2. page는 PDF 뷰어 표시 페이지 (1-based).
3. 문서에 없는 값은 모두 null.
4. raw_text가 null이면 citation, value, unit 도 null.
5. 추측 금지. 본문에 명시된 것만.

예시:
- 운용보수: {"raw_text": "집합투자업자보수율 : 연 1,000분의 8.9", "page": 15, "value": "1000분의 8.9", "unit": "permille_per_year"}

문서:
{document_pages}

JSON으로만 답하세요.
```

### 4.4 결정론 파라미터 (전 호출 통일)

| 파라미터 | 값 | 이유 |
|---|---|---|
| `model` | `gemma4:31b` | 동일 모델 hash 고정 |
| `temperature` | **0.1** | 0은 Q4 degenerate 위험 |
| `seed` | 42 | 재현성 |
| `top_p` | 1.0 | 명시적 |
| `num_predict` | 4096 | 14필드 JSON 충분 |
| 모델 hash | `ollama show gemma4:31b` 출력 로깅 | 정확한 정체성 |

---

## 5. 가드 3종 형식

스키마 단일 소스: [`INTERFACES.md`](./INTERFACES.md).

### 5.1 공통 `GuardEvent` (요지)

```python
class GuardEvent(BaseModel):
    guard: Literal["G1", "G2", "G3"]
    field_path: str | None
    decision: Literal["pass", "reject", "retry"]
    reason_code: str          # 기계 판독
    reason: str               # 사람 판독
    metadata: dict
```

### 5.2 G1 형식 가드

**입력**: 원시 LLM 출력 문자열
**출력**: `(ExtractionResult | None, list[GuardEvent])`
**전략**: Pydantic 검증 → 실패 시 1회 재시도 → 실패하면 reject

```python
def check_format(
    raw_output: str,
    schema: type[BaseModel],
    retry_callback: Callable[[str], str] | None = None,
) -> tuple[BaseModel | None, list[GuardEvent]]:
    # 1차 — markdown code fence 제거 후 검증
    cleaned = strip_markdown_fence(raw_output)
    try:
        return schema.model_validate_json(cleaned), [pass_event]
    except (json.JSONDecodeError, ValidationError) as e:
        # 2차 — LLM에 오류 피드백 후 재호출
        if retry_callback is not None:
            retry_raw = retry_callback(f"이전 응답 오류: {e}. 수정해 JSON만 답하라.")
            try:
                return schema.model_validate_json(strip_markdown_fence(retry_raw)), [retry_pass_event]
            except Exception:
                return None, [reject_event]
        return None, [reject_event_no_retry]
```

### 5.3 G2 출처 가드

**입력**: G1 통과한 `ExtractionResult` + PDF 페이지 수
**출력**: 가짜 인용 필드를 null로 만든 `ExtractionResult` + `list[GuardEvent]`
**대상 케이스**: 골든셋 C029 (page=999)

**검사 2종**:
1. **페이지 범위**: `citation.page` 가 `[1, max_page]` 안인가
2. **document 라벨 일치**: contract 측 필드의 `citation.document` 가 `"신탁계약서"` 인가, im 측은 `"IM"` 인가

> ②는 2-pass vision 호출에서 모델이 측을 헷갈리는 경우(예: contract 패스에서 `citation.document="IM"` 출력) 를 잡기 위한 추가 안전망. 결정론 검사.

```python
def check_citations(extraction, ctx) -> tuple[ExtractionResult, list[GuardEvent]]:
    for field_path, comparable in iter_comparable_fields(extraction):
        for side in ("contract", "im"):
            cv = getattr(comparable, side).citation
            if cv is None:
                continue  # raw_text 없으면 검사 대상 X
            
            # (1) 페이지 범위
            max_page = ctx.contract_pages if side == "contract" else ctx.im_pages
            if not (1 <= cv.page <= max_page):
                nullify(comparable, side)
                emit_event("G2", f"{field_path}.{side}", "reject",
                           "page_out_of_range", f"page {cv.page} ∉ [1, {max_page}]")
                continue
            
            # (2) document 라벨 일치
            expected = "신탁계약서" if side == "contract" else "IM"
            if cv.document != expected:
                nullify(comparable, side)
                emit_event("G2", f"{field_path}.{side}", "reject",
                           "citation_document_mismatch",
                           f"side={side} 인데 citation.document={cv.document}")
```

### 5.4 G3 제약 가드

**입력**: G1·G2 통과한 `ExtractionResult`
**출력**: 범위/논리 위반 필드 null + `list[GuardEvent]`
**대상 케이스**: 골든셋 C030 (운용보수 8.9%) + SHACL 위반 일반

**두 갈래**:
- (a) **결정론 Python 규칙** — 즉시 동작 가능
- (b) **SHACL 위임** — `shapes.ttl` 갱신 후 동작

```python
CONSTRAINTS = {
    "fee_schedule.management_fee": {"type": "percent_range", "min": 0.0, "max": 5.0},
    "fee_schedule.trust_fee":      {"type": "percent_range", "min": 0.0, "max": 2.0},
    "fee_schedule.sales_fee":      {"type": "percent_range", "min": 0.0, "max": 3.0},
    "fund.inception_date":         {"type": "iso_date_loose"},
    "fund.maturity_date":          {"type": "iso_date_loose"},
    "_logic": [
        {"rule": "maturity_gt_inception", "fields": ["fund.inception_date", "fund.maturity_date"]},
    ],
}

def check_constraints(extraction, ctx):
    # (a) 결정론 범위
    for field_path, comparable in iter_comparable_fields(extraction):
        rule = CONSTRAINTS.get(field_path)
        if rule:
            apply_rule(comparable, rule)
    # (b) 논리
    for logic_rule in CONSTRAINTS["_logic"]:
        apply_logic(extraction, logic_rule)
    # (c) SHACL 위임 (선택)
    if ctx.config.g3_use_shacl:
        abox = extraction_to_graph(extraction)
        shacl = validate_graph(abox)
        if not shacl.conforms:
            emit_event("G3", None, "reject", "shacl_violation", ...)
```

> ⚠️ `shapes.ttl`에 비즈니스 제약(보수 0~5% 등) 추가는 종현 W2 task. 그 전까지는 (a)로만 동작.

### 5.5 Registry (ON/OFF + 체이닝)

```python
@dataclass(frozen=True)
class GuardConfig:
    g1_format: bool = True
    g2_citation: bool = True
    g3_constraint: bool = True
    g1_max_retries: int = 1
    g3_use_shacl: bool = True

def apply_guards(raw_output, ctx, retry_callback=None) -> tuple[ExtractionResult | None, list[GuardEvent]]:
    events = []
    extraction = None
    
    if ctx.config.g1_format:
        extraction, e1 = check_format(raw_output, ExtractionResult, retry_callback)
        events.extend(e1)
        if extraction is None:
            return None, events
    else:
        extraction = ExtractionResult.model_validate_json(raw_output)  # 강제 통과
    
    if ctx.config.g2_citation:
        extraction, e2 = check_citations(extraction, ctx)
        events.extend(e2)
    
    if ctx.config.g3_constraint:
        extraction, e3 = check_constraints(extraction, ctx)
        events.extend(e3)
    
    return extraction, events
```

**3조건 매핑**:
- ② +온톨로지: `GuardConfig(False, False, False)` — 가드 OFF
- ③ +가드(풀): `GuardConfig(True, True, True)` — 가드 ON

---

## 6. 재시도 전략 (G1 한정)

| 시도 | 입력 | 처리 |
|---|---|---|
| 1 | 정상 프롬프트 + JSON Schema | Pydantic 검증 → 통과 시 종료 |
| 2 | 1차 응답 + "이전 응답에 오류 X. 수정해 JSON만 답하라" | 다시 호출 |
| 3+ | (없음) | reject + 추출 결과 null marking |

**1회만인 이유**:
- 재시도 ↑ → 비용·시간 ↑
- 2회로 못 고치면 모델 한계 — 가드 reject가 정답
- `metadata.attempt` 통계 → 약한 모델 행동 분석 가능

---

## 7. 디렉토리 구조 (최종)

```
src/
├── ingest/                          📝 (PM, 신규)
│   ├── __init__.py
│   └── pdf_to_text.py               📝 OCR + pdfplumber → PageText[]
│
├── client/
│   ├── anthropic_client.py          ✅ (종현, 있음 — 무손)
│   └── ollama_client.py             📝 (PM, 신규) Gemma HTTP 래퍼
│
├── extraction/                      ✅ (PM, 구현 완료 v0)
│   ├── __init__.py                  ✅ public API export
│   ├── side_schemas.py              ✅ FundSide·PartySide·… + SideExtraction + merge_sides()
│   └── extractor.py                 ✅ 2-pass orchestration + SYSTEM_RULES (인라인 프롬프트)
│
│   ※ 원래 plan 의 backend_base.py / backend_ollama.py 는 YAGNI 로 미구현
│     (백엔드 1개만 — OllamaClient 직접 호출). 비교 실험 필요 시 추가.
│   ※ prompts/extract_side_v1.md / retry_g1_v1.md 도 인라인 결정.
│
├── guards/                          📝 (PM, 신규)
│   ├── __init__.py
│   ├── base.py                      📝 GuardEvent, GuardConfig, Guard Protocol
│   ├── g1_format.py
│   ├── g2_citation.py
│   ├── g3_constraint.py
│   └── registry.py
│
├── pipelines/                       ✅ (종현, 있음 — 무손)
│   ├── extract.py                   ✅ (Claude 경로)
│   ├── normalize.py                 ✅
│   ├── cross_check.py               ✅
│   └── llm_judge.py                 ✅
│
├── ontology/                        ✅ (종현, 있음 — 무손)
│   ├── mapping.py                   ✅
│   └── validate.py                  ✅
│
└── schemas/
    └── extraction.py                ✅ (종현, 단일 소스 — 변경 금지)
```

**의존성 추가** (requirements.txt + pyproject.toml):
```
pdfplumber>=0.11      # 디지털 PDF 텍스트 추출
pdf2image>=1.17       # 스캔 PDF → PNG (vision 입력용)
pypdfium2>=4.30       # pdfplumber 백엔드
pytesseract>=0.3.10   # (옵션) OCR — Tesseract 시스템 설치 시
requests>=2.32        # Ollama HTTP
```

**시스템 의존성**:
- **Poppler** (pdf2image 백엔드) — `conda install -c conda-forge poppler -y` (env 내 Library/bin 에 설치 → `_find_poppler_path()` 가 자동 탐색)
- Tesseract OCR — **선택**, vision 모드 사용 시 불필요

---

## 8. 일정 (PM 본인 4주)

| 시점 | 마일스톤 | 통과 기준 |
|---|---|---|
| **D+0** (오늘) | smoke + 본 문서 + INTERFACES.md freeze | ✅ 완료 |
| **D+3** | `src/ingest/pdf_to_text.py` + 단위 테스트 | 이지스 PDF 2개 → PageText 생성 |
| **D+5** | `src/client/ollama_client.py` + `src/extraction/backend_ollama.py` | mock prompt → 한 면 추출 |
| **W2 중반** | `src/extraction/extractor.py` (2-pass) | 실제 PDF 2개 → ExtractionResult v0 |
| **W2 끝** | G1·G2 가드 + 단위 테스트 | `tests/test_guards.py` 통과 |
| **W3 초** | G3 가드 + Registry + 3조건 ON/OFF | guard_log.json 차이 출력 |
| **W3 끝** | 골든셋 30 → 추출 → 가드 → cross_check 한 줄 | 승연 채점기와 연결 |
| **W4** | 통계 분리 작업 복귀 (McNemar·Bootstrap) | — |

---

## 9. R&R 영향 (역할분담.md 갱신 필요)

| 활동 | 기존 (R/A) | 새 (R/A) |
|---|---|---|
| LLM 추출 (Claude 백엔드) | 종현 A/R | **종현 A/R** (유지) |
| LLM 추출 (Gemma 백엔드) | 없음 | **승훈 A/R** (신규) |
| 가드 3종 | 건 A/R | **승훈 A/R** |
| 변조 적용·3조건 실험 실행 | 건 A/R | **건 A/R** (유지) |
| CLI 골격 | 건 A | 건 A/R |

→ 건의 부담이 줄어 다른 영역(시각화·부트스트랩 보조) 일부 흡수 가능. 별도 협의.

---

## 10. 리스크 4종

| 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| **Gemma 4 31B 한국어 정확도 부족** | 저 | 高 | smoke 통과로 일단 안전. qwen3.5:27b 백업 |
| **Vision 입력 페이로드 (~22MB base64)** | 중 | 中 | `IMAGE_MAX_DIMENSION=1600` 다운스케일 / 필요 시 페이지 chunk 분할 |
| **Ollama JSON Schema 미준수** | 저 | 高 | smoke 검증됨. G1 재시도가 안전망 |
| **PM 시간 부족** | 고 | 高 | D+5까지 Ollama smoke 안 되면 즉시 알람. 4B로 다운그레이드 가능 |

---

## 11. 환경 운영 노트 (Windows + conda + Korean path)

소소하지만 발견한 함정 — 코드/문서 작성 시 주의:

1. **conda run 이 한글 경로·newline 인자에서 깨짐** → `C:/Users/.../envs/dnb_harness/python.exe` 직접 호출 권장
2. **Windows cp949 콘솔이 em-dash (—) 등 일부 유니코드 안 됨** → 스크립트 실행 시 `PYTHONIOENCODING=utf-8` 설정
3. **PowerShell의 curl pipe가 한글 출력 깨뜨림** → Python `requests` 직접 사용

스크립트는 `scripts/hello_gemma.py` 처럼 stand-alone로 짜고, `PYTHONIOENCODING=utf-8 <python_exe> <script.py>` 패턴으로 실행.

---

## 12. 다음 액션 (D+1)

1. **`docs/INTERFACES.md` 박기** ← 본 작업과 동시 (병렬)
2. **`src/ingest/pdf_to_text.py` 시작** — Tesseract Korean 설치 + 디지털/스캔 분기
3. **requirements.txt + pyproject.toml** 에 pdfplumber·pytesseract 추가
4. **`역할분담.md` §9 표 반영** — PM이 추출+가드 전담으로 재조정

---

## 13. 실행 보고서 — D+0 추출·정제 5단계 (2026-05-29)

> 이 섹션은 **시간순 실험 기록**. 무엇을 만들었고, 무엇을 돌렸고, 무엇을 보고, 최종 무엇을 채택했나.

### 13.1 한 줄 요약

**최초 5회 추출 → 5개 정제 작업(i~v) 순차 수행 → 최종 채택: `temperature=0.0`, `IMAGE_DPI=200`. 이지스블럭(오답) → 이지스블랙(정답) 으로 OCR 정확도 개선 확인. G2 가드 골든셋 C029 시뮬 통과.**

### 13.2 V1 — 첫 5회 추출 (baseline 실험)

**설정**:
- Backend: `gemma4:31b` (Q4_K_M, 19GB), Ollama 0.24.0
- Temperature: 0.1
- IMAGE_DPI: 150
- Seeds: [42, 1, 2, 3, 4]
- 입력: 계약서 22p (스캔→vision), IM 32p (디지털→pdfplumber)

**산출 위치**: `database/gemma4/run_NN_seedM/{extraction.json, extraction_after_guards.json, guard_log.json, meta.json}`

**결과 (5/5 성공)**:

| run | seed | wall(s) | eval(s) | guards events | rejected |
|---|--:|--:|--:|--:|--:|
| run_01 | 42 | 174 | 103 | 25 | 0 |
| run_02 | 1  | 173 | 107 | 26 | 0 |
| run_03 | 2  | 174 | 107 | 26 | 0 |
| run_04 | 3  | 173 | 107 | 26 | 0 |
| run_05 | 4  | 174 | 107 | 26 | 0 |

**발견된 문제 3개**:
1. **Vision OCR 오류**: 모든 run에서 `fund.name.contract` 가 "이지스블**럭**ON" 또는 "이지스블**루**ON" — 정답 "이지스블**랙**ON" 인식 실패
2. **필드 결측**: seed=42 run에서 `inception_date`, `sales_fee`, `is_redeemable` 가 null — 다른 seed에선 채워짐
3. **seed 간 변동**: 같은 입력인데도 seed 따라 추출 결과 달라짐 (temp=0.1 비결정론)

### 13.3 (i) error.txt 잔재 청소

**대상**: 최초 실행 시 Poppler 미설치로 실패한 흔적이 각 run 폴더에 `error.txt` 5개 잔존

**조치**:
```bash
find database/gemma4 -name "error.txt" -delete
```

**결과**: 5/5 파일 삭제 완료

### 13.4 (ii) temp=0 안전성 검증

**우려**: §4.4 표에 "temp=0은 Q4 양자화 token 폭주(degenerate) 위험" 명시

**검증 스크립트**: [`scripts/smoke_temp0.py`](../scripts/smoke_temp0.py)

**방법**: text-only 단순 prompt + 3-필드 JSON Schema. temp ∈ {0.0, 0.05, 0.1} × 같은 prompt 2회 호출 = 6번

**결과**:
| temperature | 1st call | 2nd call | eval_ms | 일치 |
|--:|---|---|--:|:--:|
| 0.0 | `{fund_name: 이지스블랙 ON 일반사모투자신탁제 1 호, mgmt: 연 1,000분의 8.9, trust: 0.5/1000 per year}` | 동일 | 3.4s / 4.4s | ✅ |
| 0.05 | (동일) | (동일) | 4.3s / 4.4s | ✅ |
| 0.1 | (동일) | (동일) | 3.7s / 3.8s | ✅ |

**결론**: **text-only 시나리오에선 temp=0이 안전** (폭주 없음, 결정론 OK). PLAN §4.4 의 우려는 text-only 한정 false alarm. Vision 입력은 별도 검증 필요 (§13.5).

### 13.5 (iii) Vision OCR 개선 — DPI 150 → 200 + temp=0

**가설 2개**:
1. DPI를 150→200으로 올리면 한국어 OCR 정확도 ↑
2. temp=0이면 추출 안정성 ↑ (필드 결측 ↓)

**검증 스크립트**: [`scripts/extract_v2.py`](../scripts/extract_v2.py)

**설정**:
- temperature=0.0, IMAGE_DPI=200
- 같은 seed=42 로 2회 실행 (run_A, run_B) — 결정론도 동시 측정

**산출 위치**: `database/gemma4_v2_t0_d200/run_{A,B}_seed42_t0_d200/`

**결과 1 — OCR 정확도 (V1 vs V2 run_A, 계약서 측)**:

| 필드 | V1 (temp=0.1, DPI=150) | V2 (temp=0, DPI=200) | 평가 |
|---|---|---|---|
| `fund.name` | 이지스블**럭**ON … | 이지스블**랙** ON … | ✅ **정답 달성** |
| `fund.type` | 일반사모집합투자기구로서 … | 일반사모투자신탁 | △ (단순화) |
| `inception_date` | null | 2025년 7월 22일 | ✅ **결측 해소** |
| `maturity_date` | 2027년 7월 22일 | 2027년 7월 22일 | ✅ 동일 정답 |
| `mgmt_fee` | 연 1,000분의 8.9 | 연 1,000분의 8.9 | ✅ |
| `trust_fee` | 연 1,000분의 0.5 | 연 1,000분의 0.5 | ✅ |
| `sales_fee` | null | 연 1,000분의 0.3 | ✅ **결측 해소** |
| `asset_manager` | 이지스자산운용 주식회사 | 이지스자산운용 주식회사 | ✅ |
| `is_redeemable` | null | 수익자는 환매를 청구할 수 없다 | ✅ **결측 해소** |

→ **DPI=200 + temp=0 으로 4 필드 추가 정답 + 펀드명 오타 해소**.

**결과 2 — Vision 결정론 (run_A vs run_B, 동일 seed=42)**:

| 필드 | run_A | run_B | 일치 |
|---|---|---|:--:|
| fund.name | 이지스블랙 ON … | 이지스블랙 ON … | ✅ |
| fund.type | 일반사모투자신탁 | 일반사모투자신탁 | ✅ |
| inception_date | 2025년 7월 22일 | 2025년 7월 22일 | ✅ |
| maturity_date | 2027년 7월 22일 | 2027년 7월 22일 | ✅ |
| mgmt_fee | 연 1,000분의 8.9 | 연 1,000분의 8.9 | ✅ |
| trust_fee | 연 1,000분의 0.5 | 연 1,000분의 0.5 | ✅ |
| **sales_fee** | 연 1,000분의 0.3 | **null** | ❌ |
| asset_manager | 이지스자산운용 주식회사 | 이지스자산운용 주식회사 | ✅ |
| is_redeemable | 환매 청구할 수 없다 | 환매 청구할 수 없다 | ✅ |
| 가드 이벤트 수 | 31 | 29 | (2 차이) |

→ **8/9 필드 결정론, 1 필드 비결정**. text-only에선 6/6 결정론이었으나 vision 입력에선 미세 비결정 발생. 원인 추정: vision attention 의 Q4 양자화 누적 부동소수점 오차 + GPU 커널의 비결정 reduction.

**완화 옵션** (지금 적용 X, 차후):
- (a) **다중 실행 후 모드값**: 같은 seed로 3회 실행 → 다수결 → 안정 추출
- (b) **temp=0.0 + flash-attention 비활성**: 비결정성 일부 줄어듦 (Ollama 옵션)
- (c) **결정론 수용**: 통계에서 다수의 실행 평균으로 처리

### 13.6 (iv) G2 가드 효과 입증 — 골든셋 C029 시뮬레이션

**대상 케이스**:
- C029 (fake_citation): `im_page = 999` (PDF에 없는 페이지)
- + 추가: `citation.document` side mismatch (contract 측인데 "IM" 라벨)

**검증 스크립트**: [`scripts/test_g2_fake_citation.py`](../scripts/test_g2_fake_citation.py)

**방법**:
1. V1 run_01 의 `extraction.json` 을 base 로 load
2. `fund.name.im.citation.page = 999` 변조
3. `party.asset_manager.contract.citation.document = "IM"` 변조
4. G2 가드만 단독 실행 (LLM 호출 0회)

**결과**:

| 변조 | G2 reason_code | 처리 |
|---|---|---|
| page=999 (max=32) | `page_out_of_range` | ✅ `fund.name.im.raw_text` → null |
| document="IM" on contract side | `citation_document_mismatch` | ✅ `party.asset_manager.contract.raw_text` → null |

총 G2 이벤트: 16 (pass=14, reject=2) — **두 변조 모두 정확히 catch + null화** ✅

→ G2 가드는 골든셋 C029 시나리오에 완벽 대응. 페이지 범위 검사 + document 라벨 검사 둘 다 결정론.

### 13.7 최종 선택 — 채택된 설정

| 항목 | 채택값 | 이전 | 근거 |
|---|---|---|---|
| `temperature` | **0.0** | 0.1 | text-only smoke 폭주 없음 + vision 정확도 ↑ + V1 결측 해소 |
| `IMAGE_DPI` | **200** | 150 | 펀드명 OCR 정확도 (이지스블랙 정답) + 4 필드 추가 추출 |
| seed | 42 (실험용 기본) | 동일 | smoke 결정론 검증된 시드 |
| G1 retry | 1회 (기본) | 동일 | INTERFACES.md 스펙 그대로 |
| G2 검사 2종 | page range + document label | page only | C029 시뮬에서 양쪽 모두 효과 확인 |
| G3 SHACL 위임 | OFF | OFF | `shapes.ttl` 비즈니스 제약 보강 (종현 W2) 후 활성화 예정 |
| Vision 결정론 | 8/9 ≈ 89% 수용 | — | 다중 실행 후 다수결 또는 통계 단계에서 처리 |

**코드 적용**:
- [`src/ingest/pdf_to_text.py`](../src/ingest/pdf_to_text.py): `IMAGE_DPI = 150` → **`200`**
- [`scripts/extract_5_runs.py`](../scripts/extract_5_runs.py): `temperature=0.1` → **`0.0`**

### 13.8 산출물 표

| 카테고리 | 파일 | 산출 시점 |
|---|---|---|
| 실험 스크립트 | [`scripts/smoke_temp0.py`](../scripts/smoke_temp0.py) | (ii) |
| 실험 스크립트 | [`scripts/extract_v2.py`](../scripts/extract_v2.py) | (iii) |
| 가드 검증 | [`scripts/test_g2_fake_citation.py`](../scripts/test_g2_fake_citation.py) | (iv) |
| 결과 (V1) | `database/gemma4/run_01~05/` (5 폴더 × 4파일) | V1 |
| 결과 (V2) | `database/gemma4_v2_t0_d200/run_{A,B}/` (2 폴더 × 4파일) | (iii) |
| 보고서 | 본 §13 | (v) |

### 13.9 미해결·후속 과제

| 항목 | 우선순위 | 책임 |
|---|---|---|
| Vision 결정론 100% 달성 — flash-attention off 또는 다중 실행 다수결 | 중 | 승훈 (W3) |
| `shapes.ttl` 비즈니스 제약 추가 → G3 SHACL 위임 활성화 | 고 | 종현 (W2) |
| IM 측(디지털) 추출 정확도 검증 — 본 보고서는 contract 측만 평가 | 중 | 승훈 (W2) |
| `fund.type` 응답 단순화 경향 ("일반사모집합투자기구로서 …" → "일반사모투자신탁") — prompt 보강으로 raw_text 보존 강제 | 저 | 승훈 (W2) |
| Tesseract 백업 OCR — vision 정확도 더 떨어지는 모델 사용 시 옵션 | 저 | 미정 |
