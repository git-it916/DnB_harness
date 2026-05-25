# 🛡️ 조건 — Guards · Ablation · Reliability

> 너의 트랙은 우리 프로젝트의 **학술적 핵심**이야.
> "LLM은 가끔 잘못 답한다 → 어떻게 안전장치(가드)로 막을 것인가" 를 **숫자로 증명**하는 트랙.
> 학술제 발표의 메인 메시지가 여기서 나온다.

---

## 1. 5분 컨셉

### 가드 (Guard) — 정확한 정의
LLM의 출력을 **그대로 믿지 않고**, 한 번 더 검증하는 후처리 단계. 통과 못 하면 reject/수정/재시도.
가드는 **LLM 호출 없이도 작동 가능한 결정론 함수**여야 함 (LLM이 LLM을 검사하면 같이 틀림).

### 환각 (Hallucination)
LLM이 그럴듯하게 보이는 **거짓 정보**를 생성하는 현상.
우리 케이스: "자본시장법 §99-7" 같은 가짜 조항 인용. 또는 PDF에 없는 수치를 자신 있게 적기.

### False Alarm (FAR) vs Missed Detection
| 종류 | 의미 | 비용 |
|------|------|------|
| False Alarm | 정상인데 위반이라고 잘못 잡음 | 분석가 시간 낭비 |
| Missed Detection | 위반인데 못 잡음 | **사고 발생** (훨씬 치명) |

가드 설계는 항상 이 둘의 트레이드오프. 우리는 missed detection을 더 무겁게 본다.

### Ablation 실험 — 너의 메인 contribution
"가드 5개를 모두 켰을 때 vs 1개씩 끄면서 측정". 어느 가드가 얼마나 효과 있는지를 표로 증명.

예시 출력:
```
| 설정          | FAR  | Missed | F1   |
|---------------|------|--------|------|
| 가드 없음     | 0.32 | 0.41   | 0.51 |
| +스키마검증   | 0.21 | 0.39   | 0.62 |
| +인용검증     | 0.15 | 0.22   | 0.78 |
| +값범위검증   | 0.12 | 0.18   | 0.83 |
| +교차검증     | 0.08 | 0.11   | 0.90 |
| 전체 ON       | 0.05 | 0.09   | 0.93 |
```

→ "인용검증 가드가 가장 큰 효과" 같은 결론이 나옴. **이게 학술제 메인 그래프**.

---

## 2. 0주차 체크리스트

- [ ] [공통 README](./README.md) 0주차 셋업 완료
- [ ] PLAN.md §4.2 (Synthetic Perturbation) §4.3 (Risk Checklist) 정독
- [ ] 종현이 만든 출력 스키마 (`src/schemas/`) 확인 — 너의 가드는 이걸 입력으로 받는다

---

## 3. 1주차: 첫 가드 1개 구현 + 가드 5종 설계 문서

### 산출물 1: `docs/guards.md` — 가드 5종 명세

각 가드에 대해 "무엇을 / 왜 / 어떻게 / 통과 기준 / 실패 시" 4줄로 정리.

```markdown
<!-- docs/guards.md -->
# 가드 5종 명세

## G1. Schema Guard (스키마 검증)
- **무엇**: LLM 출력이 Pydantic 스키마에 맞는지 검증
- **왜**: 출력 파싱 실패는 downstream 전체를 망친다
- **어떻게**: `ExtractAnchorsOutput(**llm_output)` 시도
- **실패 시**: 재시도 (max 2회), 그래도 실패하면 fail-record

## G2. Citation Guard (인용 검증)
- **무엇**: LLM이 적은 (doc, page) 가 실제 PDF에 존재하는지 검증
- **왜**: "신탁계약서 p.99" 인데 PDF가 50p면 환각
- **어떻게**: `pypdf` 로 PDF 페이지 수 확인 → 범위 안인지 체크
- **실패 시**: 해당 anchor만 reject

## G3. Range Guard (값 범위 검증)
- **무엇**: 숫자 필드가 도메인 상식 범위인지
- **왜**: 운용보수 50%, 만기 1850년 같은 명백한 오류 차단
- **어떻게**: 필드별 min/max 정의 (예: management_fee_pct ∈ [0, 5])
- **실패 시**: anchor reject + 로그

## G4. Cross-Document Guard (교차 검증)
- **무엇**: 같은 필드의 값이 3개 문서에서 일치하는지
- **왜**: 불일치는 곧 발견해야 할 모순 (우리 핵심 태스크)
- **어떻게**: doc별 값 비교, 다르면 discrepancy로 emit
- **실패 시**: report에 discrepancy 추가 (가드가 차단 X, 정보 추가)

## G5. Severity Calibration Guard (심각도 보정)
- **무엇**: LLM이 매긴 severity가 룰북과 맞는지
- **왜**: LLM은 severity를 보수적으로/공격적으로 매기는 편향이 있음
- **어떻게**: 필드별 severity 규칙 (예: 운용보수 변경 = high)
- **실패 시**: severity 덮어쓰기 + 변경 로그 기록
```

### 산출물 2: 첫 가드 구현 — G2 Citation Guard

가장 명확한 효과가 보이는 가드부터.

```python
# src/guards/citation_guard.py
from dataclasses import dataclass
from pathlib import Path
from pypdf import PdfReader

@dataclass(frozen=True)
class GuardResult:
    guard_name: str
    passed: bool
    rejected_items: list[dict]      # anchor_id 등
    notes: list[str]

class CitationGuard:
    name = "G2_citation"

    def __init__(self, pdf_paths: dict[str, Path]):
        """pdf_paths: {'핵심상품설명서': Path(...), ...} — 문서명 → 파일"""
        self.page_counts = {
            doc_name: len(PdfReader(str(p)).pages)
            for doc_name, p in pdf_paths.items()
        }

    def check(self, anchors: list[dict]) -> GuardResult:
        rejected = []
        notes = []
        for a in anchors:
            src = a.get("source")
            if not a.get("found"):
                continue  # found=False는 인용도 없음, skip
            if src is None:
                rejected.append({"anchor": a, "reason": "source missing"})
                continue
            doc = src["doc"]
            page = src["page"]
            max_page = self.page_counts.get(doc)
            if max_page is None:
                rejected.append({"anchor": a, "reason": f"unknown doc: {doc}"})
            elif not (1 <= page <= max_page):
                rejected.append({
                    "anchor": a,
                    "reason": f"page {page} out of range (1~{max_page})",
                })
        passed = len(rejected) == 0
        return GuardResult(
            guard_name=self.name,
            passed=passed,
            rejected_items=rejected,
            notes=notes,
        )
```

```python
# tests/guards/test_citation_guard.py
def test_citation_guard_rejects_out_of_range(tmp_path):
    # fixture PDF 만들기 (또는 mock PageCount)
    # 5페이지짜리 PDF에 page=99 인용 → reject
    ...
```

### DoD
- `docs/guards.md` 5종 명세 작성
- `src/guards/citation_guard.py` 동작 + 테스트 통과
- 종현이 만든 실제 출력에 가드 돌려서 reject 케이스 1개라도 잡아내기

---

## 4. 2주차: 가드 3개 추가 구현 + Ablation 실행

### 산출물 1: 가드 5종 전부 구현

각 가드는 같은 인터페이스 (`check(...) -> GuardResult`) 따르도록 합의.

```python
# src/guards/registry.py
from src.guards.citation_guard import CitationGuard
from src.guards.range_guard import RangeGuard
# ... 등등

ALL_GUARDS = {
    "G1_schema": SchemaGuard,
    "G2_citation": CitationGuard,
    "G3_range": RangeGuard,
    "G4_cross_doc": CrossDocGuard,
    "G5_severity": SeverityGuard,
}

def run_guards(anchors: list[dict], enabled: set[str], **deps) -> list[GuardResult]:
    return [
        ALL_GUARDS[name](**deps.get(name, {})).check(anchors)
        for name in ALL_GUARDS
        if name in enabled
    ]
```

### 산출물 2: Ablation 실험 스크립트

```python
# scripts/run_ablation.py
import itertools, json
from pathlib import Path
from src.guards.registry import ALL_GUARDS, run_guards
from src.eval.anchor_scorer import score_anchors  # 승훈 코드

# 1) Cumulative ablation (가드 하나씩 추가)
def cumulative_configs() -> list[set[str]]:
    names = list(ALL_GUARDS)
    return [set()] + [set(names[: i + 1]) for i in range(len(names))]

# 2) Leave-one-out (전체 - 1개)
def leave_one_out_configs() -> list[set[str]]:
    names = list(ALL_GUARDS)
    return [set(names) - {n} for n in names]

def run(predicted: list[dict], gt: list[dict], pdf_paths: dict) -> list[dict]:
    rows = []
    for cfg in cumulative_configs() + leave_one_out_configs():
        results = run_guards(predicted, enabled=cfg, citation={"pdf_paths": pdf_paths})
        # reject된 것 제외하고 채점
        kept = [a for a in predicted if not any(
            a in r.rejected_items for r in results
        )]
        _, em = score_anchors(gt, {a["field"]: a["value"] for a in kept})
        rows.append({"config": sorted(cfg), "em": em, "n_kept": len(kept)})
    return rows

if __name__ == "__main__":
    # ... 로드 + 실행 + reports/ablation/results.json 저장
    ...
```

### 산출물 3: 결과 표 + 그래프
- `reports/ablation/<run_id>/results.md` — 위 예시 같은 표
- `reports/ablation/<run_id>/figure.png` — bar chart (가드별 효과)

### DoD
- 가드 5종 모두 구현 + 단위 테스트
- Cumulative + Leave-one-out ablation 결과 표
- "어느 가드가 가장 효과적인가" 한 줄 결론 도출

---

## 5. 막히면

| 증상 | 해결 |
|------|------|
| 가드가 너무 엄격해서 다 reject 됨 | threshold 완화 또는 "경고만 띄우고 통과" 모드 추가 |
| 환각인지 정상인지 판단 모호 | 승훈/리나와 페어로 50건 spot-check → 가드 룰 보정 |
| 가드 코드가 LLM 출력 형식에 너무 종속 | 종현과 스키마 합의를 단단히. 스키마 버전 바뀌면 가드도 같이 업데이트 |
| Ablation 결과가 noise처럼 보임 | seed 고정 + 같은 input set으로 모든 config 돌렸는지 확인. 표본 30+ 권장 |
| LLM 출력이 가드에 안 걸리는데 결과는 틀림 | 가드 커버리지 부족 — 어떤 종류의 오류를 우리가 못 잡는지 분류해서 새 가드 제안 |

---

## 6. 다음에 참고할 것

- "Constitutional AI" (Anthropic 2022) — 가드/AI feedback 개념
- "RAGAS: Automated Evaluation of Retrieval Augmented Generation" — 인용 검증 평가법
- Guardrails AI 오픈소스: <https://github.com/guardrails-ai/guardrails> — 가드 패턴 레퍼런스
- sklearn 메트릭: `precision_recall_curve` 로 threshold tradeoff 시각화 가능
