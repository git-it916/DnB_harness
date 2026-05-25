# 🧭 신승훈 (Lead) — PM · 하네스 코어 · 골든셋

> 너는 PM이자 하네스 코어 책임자. **"이 LLM이 얼마나 잘하나"를 숫자로 증명**할 수 있게 만드는 게 네 역할.
> 코어 코드(eval/scorer) + 라벨링 + API 통합을 짊어진다.

---

## 1. 5분 컨셉

### 골든셋 (Ground Truth) — 왜 필수인가?
"느낌상 잘하더라"는 학술 발표에서 안 통한다. 골든셋이 있어야 "F1 0.91" 같은 숫자가 나온다.
**골든셋의 정확성 = 연구의 신뢰성**. 한 줄이라도 사람이 책임지고 라벨링한 데이터.

### 앵커 사실 (Anchor Facts)
펀드 1개당 25~35개. 펀드명·운용사·신탁업자·설정일·만기·기준가·운용보수·판매보수·환매조건·해지조건·자산구성 등.
이걸 YAML로 정리한 것이 우리의 1차 골든셋.

### Scorer (채점기)
LLM 답과 골든셋을 비교해 점수를 내는 **순수 함수**.
중요: LLM 호출 금지 (재현 안 됨). 입력 같으면 항상 같은 출력.

### Precision / Recall / F1
| | 의미 | 우리 케이스 예 |
|---|---|---|
| Precision | 잡은 것 중 진짜 비율 | LLM이 "위반 10건" 잡았는데 8건만 진짜 위반 → 0.8 |
| Recall | 진짜 중 잡은 비율 | 진짜 위반 20건 중 LLM이 8건 찾음 → 0.4 |
| F1 | 둘의 조화평균 | 0.8과 0.4의 F1 = 0.53 |

### Prompt Caching — 왜 PM이 알아야 하나?
펀드 1개당 PDF 3개 = 입력 토큰 수십만. 매번 다시 보내면 펀드 1개 분석에 $5+. 캐시 쓰면 $0.5 이하.
**우리 비용 가설(H3)** 의 핵심. 잘못 쓰면 비용이 10배 차이.

---

## 2. 0주차 체크리스트

- [ ] [공통 README](./README.md) 의 0주차 셋업 완료 (env, .env, hello_claude.py)
- [ ] `database/이지스 블랙ON 1호_준감필.pdf` 한 번 열어보고 펀드 구조 파악 (운용사, 신탁업자, 보수 구조 등)
- [ ] `database/.gitkeep` 빼고 PDF 자체는 절대 git에 안 들어가는지 확인 (`.gitignore` 점검)

---

## 3. 1주차: 라벨링 + Scorer 1개

### 목표
이지스 블랙ON 1호의 앵커 사실 **10개만 먼저 라벨링** + 그것을 채점하는 가장 단순한 scorer 1개 작성.

### 산출물 1: `database/labels/igis_blackon_1/anchors.yaml`

PDF 열고, 다음과 같이 항목 하나하나 손으로 찾아 입력. **출처(어느 문서 몇 페이지)** 도 반드시 기록.

```yaml
# database/labels/igis_blackon_1/anchors.yaml
fund_id: igis_blackon_1
fund_display_name: "이지스 블랙ON 일반사모투자신탁제1호"
labeler: "shin_seunghun"
labeled_at: "2026-05-28"

anchors:
  - id: a01
    field: fund_name
    value: "이지스 블랙ON 일반사모투자신탁제1호"
    type: string
    source:
      doc: "핵심상품설명서"
      page: 1

  - id: a02
    field: trust_manager       # 집합투자업자 (운용사)
    value: "이지스자산운용주식회사"
    type: string
    source:
      doc: "핵심상품설명서"
      page: 2

  - id: a03
    field: trustee             # 신탁업자
    value: "<신탁업자명 — PDF에서 확인>"
    type: string
    source:
      doc: "신탁계약서"
      page: 1

  - id: a04
    field: management_fee_pct  # 운용보수 (연 %)
    value: 0.7                  # 숫자로! 문자열 X
    unit: "percent_per_year"
    type: number
    source:
      doc: "핵심상품설명서"
      page: 5

  - id: a05
    field: inception_date
    value: "2025-07-22"
    type: date_iso
    source:
      doc: "신탁계약서"
      page: 1

  # ... 10개 채울 때까지 반복
```

**팁**:
- 숫자는 따옴표 없이 (`0.7`), 날짜는 ISO 형식 (`"2025-07-22"`).
- 못 찾으면 `value: null` + `note: "PDF에서 못 찾음"` 으로 기록.
- 3종 문서에서 같은 값이 등장하면 가장 정식 문서 (신탁계약서 > 핵심상품설명서 > 투자제안서) 를 source로.

### 산출물 2: 가장 단순한 scorer 1개

```python
# src/eval/anchor_scorer.py
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class AnchorMatch:
    anchor_id: str
    field: str
    expected: Any
    predicted: Any
    is_correct: bool

def normalize(value: Any) -> Any:
    """비교 전 정규화. 숫자 0.7 vs '0.7%' vs '0.70' 같은 표면 차이 흡수."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().rstrip("%").replace(",", "")
    return value

def score_anchors(
    gt: list[dict],          # anchors.yaml 의 anchors 리스트
    predicted: dict,         # LLM이 뱉은 { field: value, ... }
) -> tuple[list[AnchorMatch], float]:
    """앵커별 정답 여부 + Exact Match 비율 반환."""
    matches = []
    for a in gt:
        exp = normalize(a["value"])
        pred = normalize(predicted.get(a["field"]))
        matches.append(AnchorMatch(
            anchor_id=a["id"],
            field=a["field"],
            expected=exp,
            predicted=pred,
            is_correct=(exp == pred),
        ))
    em = sum(m.is_correct for m in matches) / len(matches) if matches else 0.0
    return matches, em
```

```python
# tests/test_anchor_scorer.py — 함께 만들어 두자
from src.eval.anchor_scorer import score_anchors

def test_exact_match_all_correct():
    gt = [
        {"id": "a01", "field": "fund_name", "value": "X 펀드"},
        {"id": "a02", "field": "management_fee_pct", "value": 0.7},
    ]
    pred = {"fund_name": "X 펀드", "management_fee_pct": 0.7}
    _, em = score_anchors(gt, pred)
    assert em == 1.0

def test_em_with_partial():
    gt = [{"id": "a01", "field": "fund_name", "value": "X"}]
    pred = {"fund_name": "Y"}
    _, em = score_anchors(gt, pred)
    assert em == 0.0
```

### DoD (이번 주 끝났다고 말할 기준)
- `anchors.yaml` 에 10개 항목 채워짐
- `pytest tests/test_anchor_scorer.py` 통과
- PR 1개 머지

---

## 4. 2주차: 25~35개로 확장 + Anthropic 클라이언트 래퍼

### 산출물 1: 라벨 25~35개 완성
조건과 페어로 진행. 둘이 따로 라벨링 → 차이나는 항목만 토론 → 합의안 채택 → Cohen's κ 계산.

### 산출물 2: `src/client/anthropic_client.py` — Caching + 재시도 + 사용량 로깅

```python
# src/client/anthropic_client.py — 골격
import base64
from pathlib import Path
from typing import Any
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

class HarnessClient:
    """모든 LLM 호출은 이 래퍼를 거친다. usage 로깅과 caching을 강제."""

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic()
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def call_with_pdfs(
        self,
        system_prompt: str,
        pdfs: list[Path],          # 3개 PDF 경로
        user_message: str,
        tools: list[dict] | None = None,
    ) -> dict:
        # PDF → base64 → document block (cache_control: ephemeral)
        pdf_blocks = []
        for p in pdfs:
            pdf_b64 = base64.standard_b64encode(p.read_bytes()).decode()
            pdf_blocks.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                "cache_control": {"type": "ephemeral"},  # ← 캐싱 핵심
            })

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": pdf_blocks + [{"type": "text", "text": user_message}],
            }],
            tools=tools or [],
        )

        # usage 메타 로깅 (caching 동작 확인용)
        u = resp.usage
        meta = {
            "model": self.model,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0),
        }
        return {"response": resp, "usage": meta}
```

**확인 방법**: 같은 호출을 1분 안에 두 번 하면 두 번째 호출의 `cache_read_input_tokens` 가 0이 아니어야 함. 0이면 caching이 안 걸린 것.

### DoD
- `anchors.yaml` 25~35개 완료
- Cohen's κ ≥ 0.7 (조건과의 라벨 일치도)
- 같은 PDF 2회 호출 시 cache hit 확인 (콘솔에 토큰 수 출력)
- 베이스라인 측정 결과 1부 (`reports/baseline_sonnet_46/results.md`)

---

## 5. 막히면

| 증상 | 해결 |
|------|------|
| PDF가 너무 커서 토큰 한도 넘김 | `pypdf` 로 페이지 분할, 또는 `pdf2image` 로 이미지화 후 압축 |
| LLM이 YAML 필드명을 자기 멋대로 바꿈 | 종현에게 tool-use 스키마 요청 (구조화 출력 강제) |
| Cache hit이 안 됨 | (1) 5분 TTL 지났는지, (2) `cache_control` 위치가 변하는 부분 뒤에 있는지, (3) `extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}` 필요한지 SDK 버전 확인 |
| κ 가 0.5도 안 나옴 | 라벨링 가이드(`docs/labeling_guide.md`)가 너무 모호한 것. 조건과 함께 가이드 다시 작성 |

---

## 6. 다음에 참고할 것

- Anthropic Prompt Caching 공식: <https://docs.claude.com/en/docs/build-with-claude/prompt-caching>
- Anthropic PDF Support: <https://docs.claude.com/en/docs/build-with-claude/pdf-support>
- scikit-learn metrics: `from sklearn.metrics import precision_recall_fscore_support, cohen_kappa_score`
