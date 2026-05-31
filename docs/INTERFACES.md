# 인터페이스 스펙 (단일 진실 소스)

> 팀이 병렬 작업하려면 *경계*가 먼저 박혀야 한다. 이 문서가 깨지면 모든 모듈이 깨짐.
> 변경은 PR + PM 승인. 최종 갱신: 2026-05-29.
>
> 관련: [`ARCHITECTURE.md`](./ARCHITECTURE.md) · [`extract_guard_plan.md`](./reference/extract_guard_plan.md) · [`GOLDENSET.md`](./GOLDENSET.md).

---

## 1. 인터페이스 지도

```
                     ┌──────────────────────┐
종현 (Claude)  ───→  │  ExtractionResult    │  ←─── 승훈 (Gemma)
                     │  (단일 출력 형식)    │
                     └──────────────────────┘
                              ↓
                     ┌──────────────────────┐
                     │  GuardConfig         │  ←─── 승훈 (가드 ON/OFF)
                     │  GuardEvent          │
                     │  GuardContext        │
                     └──────────────────────┘
                              ↓
                     ┌──────────────────────┐
                     │  HarnessResult       │  ←─── 건 (3조건 러너)
                     └──────────────────────┘
                              ↓
                     ┌──────────────────────┐
                     │  score.json schema   │  ←─── 승연 (채점)
                     │  manifest.json schema│
                     │  compare.md schema   │
                     └──────────────────────┘
                              ↓
                     ┌──────────────────────┐
                     │  통계 입력 표        │  ←─── 승훈 (McNemar·CI)
                     └──────────────────────┘
```

---

## 2. `LLMBackend` Protocol — 추출 백엔드 추상화

위치: `src/extraction/backend_base.py` (📝 PM 신규)

```python
from typing import Protocol
from pathlib import Path
from pydantic import BaseModel
from src.schemas.extraction import ExtractionResult, FundExtraction, PartyExtraction, FeeScheduleExtraction, RedemptionTermsExtraction

class LLMBackend(Protocol):
    """추출용 LLM 백엔드. Claude(종현) / Gemma(승훈) 모두 이거 구현."""
    name: str                       # "claude-sonnet-4-5" | "gemma4:31b"
    model_id: str                   # 정확한 model hash
    
    def extract_side(
        self,
        document_text: str,         # "[Page N]\\n<text>" 형식
        side: str,                  # "contract" | "im"
        schema: type[BaseModel],    # FundExtraction 등
    ) -> tuple[BaseModel, dict]:
        """한 면(document) × 4개념 추출.
        
        Returns:
            (parsed_result, metadata) — metadata 는 {tokens, latency_ms, raw_text}
        """
        ...
    
    def judge_equivalence(
        self,
        contract_text: str,
        im_text: str,
        field_label: str,
    ) -> tuple[bool, str, dict]:
        """의미 동등 판단 (cross_check의 needs_review 케이스).
        
        Returns:
            (is_equivalent, reason, metadata)
        """
        ...
```

**구현체**:
- `backend_anthropic.py` (종현 기존 모듈 wrapper)
- `backend_ollama.py` (PM 신규)

---

## 3. Guard 인터페이스 — `GuardEvent`, `GuardConfig`, `GuardContext`

위치: `src/guards/base.py` (📝 PM 신규)

```python
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from pydantic import BaseModel, ConfigDict
from dataclasses import dataclass

class GuardDecision(StrEnum):
    PASS = "pass"
    REJECT = "reject"
    RETRY = "retry"          # G1 전용

class GuardEvent(BaseModel):
    """가드 1회 실행의 결과 단위. 가드 로그는 list[GuardEvent]."""
    model_config = ConfigDict(extra="forbid")
    
    guard: str               # "G1" | "G2" | "G3"
    field_path: str | None   # "fee_schedule.management_fee.contract" | None for global
    decision: GuardDecision
    reason_code: str         # 기계 판독: "page_out_of_range" 등
    reason: str              # 사람 판독
    metadata: dict[str, Any] = {}

@dataclass(frozen=True)
class GuardConfig:
    """3조건 실험의 가드 토글."""
    g1_format: bool = True
    g2_citation: bool = True
    g3_constraint: bool = True
    g1_max_retries: int = 1
    g3_use_shacl: bool = True

@dataclass(frozen=True)
class GuardContext:
    """가드 실행에 필요한 외부 정보."""
    contract_pdf: Path
    im_pdf: Path
    contract_pages: int      # pypdf로 미리 계산
    im_pages: int
    config: GuardConfig

class Guard(Protocol):
    name: str                # "G1" | "G2" | "G3"
    def check(self, extraction, ctx: GuardContext) -> tuple:
        """(modified_extraction, list[GuardEvent]) 반환.
        - extraction은 deep copy 후 수정 (불변 보존).
        - reject 발생 시 해당 field의 DocumentValue를 null화.
        """
        ...
```

**guard_log.json 출력 형식**:
```json
{
  "run_id": "...",
  "guard_config": {"g1_format": true, "g2_citation": true, "g3_constraint": true, ...},
  "events": [
    {"guard": "G1", "field_path": null, "decision": "pass", "reason_code": "json_valid", "reason": "schema OK", "metadata": {}},
    {"guard": "G2", "field_path": "fund.name.im", "decision": "reject", "reason_code": "page_out_of_range", "reason": "page 999 ∉ [1, 24]", "metadata": {"page": 999, "max_page": 24}},
    {"guard": "G3", "field_path": "fee_schedule.management_fee.im", "decision": "reject", "reason_code": "percent_range", "reason": "8.9% > 5.0%", "metadata": {"value": 8.9, "max": 5.0}}
  ],
  "summary": {"total": 14, "passed": 12, "rejected": 2, "retried": 0}
}
```

---

## 4. `HarnessResult` — 하네스 1회 실행 출력

위치: `src/harness/pipeline.py` (📝 W3, 건/PM)

```python
from pydantic import BaseModel
from typing import Literal
from rdflib import Graph
from src.schemas.extraction import ExtractionResult
from src.pipelines.cross_check import CrossCheckResult

class HarnessResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    
    mode: Literal["baseline", "onto", "guard"]
    extraction: ExtractionResult       # 항상
    guard_log: list[GuardEvent] = []   # guard 모드만
    abox_ttl: str | None = None        # onto/guard 모드만 — Turtle 직렬화
    shacl_conforms: bool | None = None
    shacl_report_text: str | None = None
    cross_check: list[CrossCheckResult] | None = None  # onto/guard 모드만
    
    # 운영 메타
    total_latency_ms: int
    llm_call_count: int
    llm_total_tokens: int
    llm_total_cost_usd: float = 0.0    # local model은 0, Claude는 계산
```

---

## 5. `manifest.json` — 1회 실행의 모든 메타

위치: `reports/<run_id>/manifest.json` (자동 생성)

```json
{
  "schema_version": "v0",
  "run_id": "exp_baseline_20260601_120000_a1b2",
  "mode": "baseline",
  "guards": {
    "g1_format": false,
    "g2_citation": false,
    "g3_constraint": false
  },
  "backend": {
    "name": "gemma4:31b",
    "model_id": "6316f0629137",
    "temperature": 0.1,
    "seed": 42,
    "num_predict": 4096,
    "context_length": 262144,
    "quantization": "Q4_K_M"
  },
  "inputs": {
    "contract_pdf": "database/제정신탁계약서_날인본_….pdf",
    "contract_sha256": "...",
    "contract_pages": 22,
    "im_pdf": "database/이지스 블랙ON 1호_준감필.pdf",
    "im_sha256": "...",
    "im_pages": 24
  },
  "golden_version": "v0.1",
  "started_at": "2026-06-01T12:00:00Z",
  "ended_at":   "2026-06-01T12:03:45Z",
  "total_latency_s": 225.0,
  "llm_call_count": 2,
  "llm_total_tokens": 18230,
  "cost_usd": 0.0
}
```

---

## 6. `score.json` — 채점기 출력 (승연 산출)

위치: `reports/<run_id>/score.json`

```json
{
  "schema_version": "v0",
  "run_id": "exp_baseline_20260601_120000_a1b2",
  "mode": "baseline",
  "golden_version": "v0.1",
  "n_cases": 30,
  
  "metrics": {
    "accuracy": 0.65,
    "precision": 0.71,
    "recall": 0.58,
    "f1": 0.64,
    "hallucination_rate": 0.12
  },
  
  "confusion": {
    "tp": 14,
    "fp": 6,
    "fn": 10,
    "tn": 22,
    "missing_excluded": 8
  },
  
  "by_field": {
    "fund.name":                    {"n": 8, "correct": 6, "recall": 0.75, "f1": 0.80},
    "fee_schedule.management_fee":  {"n": 8, "correct": 3, "recall": 0.25, "f1": 0.40}
  },
  
  "by_difficulty": {
    "easy":   {"n": 10, "accuracy": 1.00, "recall": 1.00},
    "medium": {"n": 24, "accuracy": 0.75, "recall": 0.70},
    "hard":   {"n": 26, "accuracy": 0.31, "recall": 0.20}
  },
  
  "by_mutation": {
    "decimal_shift":   {"n": 4, "caught": 0, "recall": 0.00},
    "fake_citation":   {"n": 2, "caught": 0, "recall": 0.00},
    "shacl_violation": {"n": 2, "caught": 0, "recall": 0.00}
  },
  
  "by_signal": {
    "normalization":       {"expected": 14, "caught": 10, "hit_rate": 0.71},
    "g2_citation":         {"expected": 2,  "caught": 0,  "hit_rate": 0.00},
    "g3_constraint+shacl": {"expected": 2,  "caught": 0,  "hit_rate": 0.00}
  },
  
  "cases": [
    {
      "case_id": "C020",
      "field": "fee_schedule.trust_fee",
      "gold_label": "mismatch",
      "predicted_label": "match",
      "correct": false,
      "final_status": "exact_match",
      "reason_code": "raw_text_exact_match",
      "guard_rejections": [],
      "latency_ms": 1240
    }
  ]
}
```

> **gold_label ↔ FinalCheckStatus 매핑**: `GOLDENSET.md §7` 참고.

---

## 7. `compare_*.md` — 3조건 비교 리포트 (승연 산출)

위치: `reports/compare_<prefix>.md`

```markdown
# 3조건 비교 (n=30, golden=v0.1, model=gemma4:31b, seed=42)

## 핵심 지표
| 조건 | Accuracy | Precision | Recall ★ | F1 | 환각률 | 비용($) | 시간(s) |
|---|--:|--:|--:|--:|--:|--:|--:|
| ① baseline | 0.42 | 0.40 | 0.33 | 0.36 | 0.25 | 0.00 | 24 |
| ② +onto    | 0.71 | 0.69 | 0.67 | 0.68 | 0.08 | 0.00 | 31 |
| ③ +guard   | 0.85 | 0.83 | 0.83 | 0.83 | 0.00 | 0.00 | 35 |

## 통계 (PM 채울 자리)
- McNemar p-value (③ vs ①): __
- Bootstrap 95% CI on F1 (③):  [__, __]

## 난이도별 Recall
| 난이도 | n | ① | ② | ③ | Δ(③-①) |
|---|--:|--:|--:|--:|--:|
| hard | 13 | 0.15 | 0.50 | 0.80 | **+0.65** |

## 변조 유형별 Recall (12종)
| mutation_type | n | ① | ② | ③ | 어디가 잡았나 |
|---|--:|--:|--:|--:|---|
| decimal_shift   | 2 | 0.00 | 0.50 | 1.00 | 정규화 |
| fake_citation   | 1 | 0.00 | 0.00 | 1.00 | **G2 가드만** |
| shacl_violation | 1 | 0.00 | 0.00 | 1.00 | **G3/SHACL만** |

## 자주 놓친 케이스 (FN)
| case_id | field | mutation | ① | ② | ③ |
|---|---|---|:--:|:--:|:--:|
| C020 | fee.trust_fee | decimal_shift | ✗ | ✓ | ✓ |
| C029 | fund.name | fake_citation | ✗ | ✗ | ✓ |
| C030 | fee.management_fee | shacl_violation | ✗ | ✗ | ✓ |
```

---

## 8. 통계 입력 표 — McNemar 페어링 (PM)

위치: `reports/stats/<run_prefix>.csv`

| case_id | gold_label | mode_baseline | mode_onto | mode_guard |
|---|---|---|---|---|
| C001 | match | match | match | match |
| C002 | match | mismatch | match | match |
| ... |

→ McNemar는 (mode_baseline vs mode_guard) 같은 짝지은 합격/불합격 차이의 유의성. 부트스트랩은 mode별 F1 분포의 95% CI.

---

## 9. 인터페이스 변경 절차

1. PR 제목: `[INTERFACE] <스키마명> 변경`
2. body에 *영향 모듈 목록* 명시 (예: extractor·guards·scorer·러너 중 어디)
3. PM 승인 필수
4. 변경 후 `docs/reference/extract_guard_plan.md`·`docs/GOLDENSET.md` 동기화

---

## 10. 변경 이력

| 버전 | 날짜 | 변경 | 작성 |
|---|---|---|---|
| v0.1 | 2026-05-29 | 초안 — 7개 인터페이스 freeze | 승훈 |
