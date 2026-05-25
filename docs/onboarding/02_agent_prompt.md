# 🧠 노종현 — Agent & Prompt Architect

> 너는 "LLM에 무엇을 어떻게 묻고, 어떤 형태로 답받을 것인가" 책임자.
> 우리 시스템에서 LLM이 일관된 답을 내도록 만드는 핵심 영역이고, 학술적 깊이가 가장 필요한 트랙.

---

## 1. 5분 컨셉

### System Prompt vs User Message
- **System**: "너는 한국 사모펀드 DD 전문가야. 다음 규칙을 지켜라." 같은 **역할·규칙·페르소나**.
- **User**: 매번 바뀌는 실제 질문. ("이 펀드의 운용보수를 알려줘")
- 캐싱 관점: system은 거의 안 바뀌므로 캐시. user는 매번 새로 보냄.

### Few-shot Prompting
"이런 입력엔 이런 출력을 내야 해" 예시 2~3개를 system prompt에 박아넣는 기법.
모델이 출력 형식을 따르도록 만드는 가장 비용 낮은 방법.

### Structured Output (Tool Use)
자유 텍스트로 답받으면 파싱이 깨진다. Anthropic의 `tools` 파라미터로 **JSON 스키마를 강제**.
→ "스키마에 맞춰서만 답해" → 후속 코드가 안정적으로 파싱 가능.

### Prompt Versioning
프롬프트 한 줄 바꾸면 결과 바뀜. 그러면 "어제 측정한 0.91" 과 "오늘 측정한 0.88" 을 비교할 수 없다.
→ 모든 프롬프트에 **버전 번호** + 모든 결과에 `prompt_version` 메타 기록.

### RAG (필요시)
PDF 3종이 너무 크면 → 사전에 관련 페이지만 골라 LLM에 넘기는 기법.
**우리는 일단 RAG 없이 시작** (Claude는 long-context, PDF 전체 잘 처리). Phase 3쯤 비용 보고 도입 결정.

---

## 2. 0주차 체크리스트

- [ ] [공통 README](./README.md) 0주차 셋업 완료
- [ ] `scripts/hello_claude.py` 동작 확인
- [ ] Anthropic SDK 공식 문서 빠르게 훑기 (특히 `tools` 파라미터)
  - <https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview>

---

## 3. 1주차: 첫 프롬프트 + Pydantic 스키마

### 목표
**앵커 사실 추출 태스크 v0** 한 개를 끝까지 (system prompt → schema → 호출 → 파싱) 동작시키기.

### 산출물 1: `prompts/v0/extract_anchors/system.md`

```markdown
<!-- prompts/v0/extract_anchors/system.md -->
당신은 한국 사모펀드 문서를 분석하는 Due Diligence 전문가입니다.
사용자가 제공한 펀드 관련 PDF 3종(핵심상품설명서·투자제안서·신탁계약서)에서
요청된 핵심 사실을 추출하여 `extract_anchors` 도구로 반환하세요.

규칙:
1. 모든 값은 PDF에 명시된 그대로 추출하세요. 추론·해석 금지.
2. 숫자는 단위를 분리: "연 0.7%" → value: 0.7, unit: "percent_per_year"
3. 날짜는 ISO 형식: "2025년 7월 22일" → "2025-07-22"
4. 문서에서 찾을 수 없으면 value: null, found: false 로 표시.
5. 각 사실에 출처(어느 문서 몇 페이지)를 반드시 명시.

예시 (few-shot):
  요청: management_fee_pct (운용보수 연 %)
  추출: { value: 0.7, unit: "percent_per_year", found: true,
          source: { doc: "핵심상품설명서", page: 5 } }
```

### 산출물 2: `src/schemas/anchor_extraction.py`

```python
# src/schemas/anchor_extraction.py
from pydantic import BaseModel, Field
from typing import Literal

SCHEMA_VERSION = "v0.1"

class Source(BaseModel):
    doc: Literal["핵심상품설명서", "투자제안서", "신탁계약서"]
    page: int = Field(ge=1)

class ExtractedAnchor(BaseModel):
    field: str                        # "management_fee_pct"
    value: str | float | int | None   # 자유 타입 (스키마는 호출 시점에 더 엄격하게)
    unit: str | None = None
    found: bool
    source: Source | None = None      # found=False면 null 허용
    note: str | None = None           # LLM이 애매하다고 느낀 부분 설명

class ExtractAnchorsOutput(BaseModel):
    schema_version: str = SCHEMA_VERSION
    anchors: list[ExtractedAnchor]
```

### 산출물 3: Anthropic tool-use 호출 코드

```python
# src/pipelines/extract_anchors_v0.py
import json
from pathlib import Path
from src.client.anthropic_client import HarnessClient
from src.schemas.anchor_extraction import ExtractAnchorsOutput

PROMPT_VERSION = "v0"

def load_prompt() -> str:
    return Path("prompts/v0/extract_anchors/system.md").read_text(encoding="utf-8")

# tools 파라미터 — JSON Schema 강제
TOOL_SPEC = [{
    "name": "extract_anchors",
    "description": "PDF에서 추출한 앵커 사실 목록을 반환합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "anchors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "value": {},  # any
                        "unit": {"type": ["string", "null"]},
                        "found": {"type": "boolean"},
                        "source": {
                            "type": ["object", "null"],
                            "properties": {
                                "doc": {"type": "string", "enum": ["핵심상품설명서", "투자제안서", "신탁계약서"]},
                                "page": {"type": "integer", "minimum": 1},
                            },
                            "required": ["doc", "page"],
                        },
                        "note": {"type": ["string", "null"]},
                    },
                    "required": ["field", "value", "found"],
                },
            },
        },
        "required": ["anchors"],
    },
}]

def run_extract(fund_id: str, requested_fields: list[str]) -> ExtractAnchorsOutput:
    client = HarnessClient(model="claude-sonnet-4-6")
    pdfs = [
        Path(f"database/{fund_id}/핵심상품설명서.pdf"),
        Path(f"database/{fund_id}/투자제안서.pdf"),
        Path(f"database/{fund_id}/신탁계약서.pdf"),
    ]
    user_msg = (
        "다음 필드들을 위 PDF 3종에서 추출하세요:\n"
        + "\n".join(f"- {f}" for f in requested_fields)
    )
    result = client.call_with_pdfs(
        system_prompt=load_prompt(),
        pdfs=pdfs,
        user_message=user_msg,
        tools=TOOL_SPEC,
    )
    # tool_use 블록에서 JSON 꺼내기
    for block in result["response"].content:
        if block.type == "tool_use" and block.name == "extract_anchors":
            return ExtractAnchorsOutput(**block.input)
    raise RuntimeError("LLM이 tool을 호출하지 않음")
```

### 동작 확인

```python
# scripts/try_extract.py
from src.pipelines.extract_anchors_v0 import run_extract

out = run_extract("igis_blackon_1", ["fund_name", "management_fee_pct", "inception_date"])
for a in out.anchors:
    print(a.model_dump())
```

### DoD
- `prompts/v0/extract_anchors/system.md` 작성
- `src/schemas/anchor_extraction.py` Pydantic 모델 정의
- `scripts/try_extract.py` 실행 → tool_use 응답으로 3개 필드 추출 성공
- LLM이 항상 tool을 호출하도록 system prompt 다듬기 (자유 텍스트로 답하면 실패)

---

## 4. 2주차: 일관성 검증 태스크 + 프롬프트 평가

### 산출물 1: 일관성 검증 프롬프트 (Consistency Task)

3종 문서 간 모순을 LLM이 찾도록 하는 두 번째 태스크. 같은 패턴으로 `prompts/v0/check_consistency/` 만들기.

핵심 스키마 (조건과 합의 필요):
```python
class Discrepancy(BaseModel):
    field: str                       # 모순난 필드
    values_by_doc: dict[str, str]    # {"핵심상품설명서": "0.7%", "투자제안서": "0.75%"}
    severity: Literal["low", "medium", "high"]
    evidence: list[Source]
    confidence: float = Field(ge=0, le=1)

class ConsistencyReport(BaseModel):
    schema_version: str = "v0.1"
    discrepancies: list[Discrepancy]
```

### 산출물 2: 프롬프트 A/B 측정

같은 태스크에 대해 프롬프트 2가지 버전 (`v0` vs `v0_b`) 만들어서 추출 정확도 비교.
승훈이 만든 scorer로 채점 → 표 1장. 이게 너의 "프롬프트 엔지니어링 실적".

```
| prompt_version | EM   | 시간 | 토큰  |
|----------------|------|------|-------|
| v0             | 0.74 | 18s  | 2.1k  |
| v0_b (CoT 추가)| 0.83 | 26s  | 3.4k  |
```

### DoD
- 두 번째 태스크(일관성) 프롬프트 + 스키마 + 호출 코드 동작
- 프롬프트 A/B 측정 결과 1장 (어느 게 좋은지 + 왜)
- 조건과 LLM 출력 스키마 최종 합의 (그 사람이 가드 입력으로 받음)

---

## 5. 막히면

| 증상 | 해결 |
|------|------|
| LLM이 tool 안 부르고 일반 텍스트로 답함 | `tool_choice={"type": "tool", "name": "extract_anchors"}` 로 강제 호출 |
| 스키마 validation error 자주 남 | `Pydantic` 의 `ValidationError` 메시지 그대로 LLM에 다시 보내서 재시도 (self-correction loop) |
| 페이지 번호를 자꾸 틀리게 적음 | system prompt에 "page번호는 PDF 좌측 하단 인쇄된 숫자가 아니라 1부터 세는 물리적 페이지" 명시 |
| 같은 질문인데 매번 다른 답 | `temperature=0` 설정, 또는 self-consistency로 N번 호출 후 다수결 |
| 한국어 필드명 vs 영어 필드명 혼용 | 스키마에서 `Literal` 로 영어 식별자 강제 (display label은 별도) |

---

## 6. 다음에 참고할 것

- Anthropic Tool Use: <https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview>
- Pydantic v2 모델: <https://docs.pydantic.dev/latest/concepts/models/>
- Anthropic Prompt Engineering: <https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview>
- 읽으면 좋은 논문: "Self-Consistency Improves Chain of Thought Reasoning" (Wang et al., 2022)
