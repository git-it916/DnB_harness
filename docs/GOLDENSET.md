# 골든셋 마스터 시트 스펙 (`golden_master.csv`)

> 채점기·통계의 **단일 진실 소스**. 이 시트가 바뀌면 모든 점수가 바뀐다.
> 파일: [`tests/golden/golden_master.csv`](../tests/golden/golden_master.csv)
> 관련 문서: [`ARCHITECTURE.md §6`](./ARCHITECTURE.md), [`ROADMAP.md §4`](./ROADMAP.md)

---

## 1. 목적

신탁계약서·IM(투자제안서)에서 **무엇을 일치로 보고 무엇을 불일치로 봐야 하는지**의 정답표.

- ① 베이스라인(LLM 단독) / ② +온톨로지(진단) / ③ +가드(집행) 의 **재현율·정밀도·F1** 을 동일 시트로 채점.
- 두 라벨러(리나·승훈)가 따로 채점 → **Cohen's κ ≥ 0.7** 충족 시 PM이 최종 확정(freeze).
- freeze 이후 변경은 **PR + PM 승인**.

---

## 2. 파일 형식

| 항목 | 값 |
|---|---|
| 인코딩 | **UTF-8 with BOM** (Excel 친화, Python은 `encoding="utf-8-sig"` 필수) |
| 구분자 | `,` (콤마) |
| 인용 | RFC 4180 — 콤마·줄바꿈·이중인용 포함 시 `"..."` 로 감싸기 |
| 헤더 | 1행 (14컬럼) |
| 본문 | 80행 (정상 35 + 변조 45) |
| 줄바꿈 | LF |

> **금지**: BOM 제거(Excel에서 한글 깨짐), 행 정렬·재번호화(case_id 안정성 깨짐), Excel "다른 이름으로 저장"으로 CSV 재출력(콤마 escape 깨질 수 있음).

---

## 3. 컬럼 명세 (14개)

| # | 컬럼 | 타입 | 필수 | 설명 |
|--:|---|---|:--:|---|
| 1 | `case_id` | `C\d{3}` | ✅ | 안정 식별자. 한 번 부여하면 영구. 삭제 시 빈 자리 두기(재번호 금지). |
| 2 | `category` | `정상` \| `변조` | ✅ | 정상=원본 의도대로, 변조=IM 값 치환. 본 문서 §5.2 |
| 3 | `field` | dotted path | ✅ | [`cross_check.py`](../src/pipelines/cross_check.py)의 [`FIELD_LABELS`](../src/pipelines/cross_check.py#L73-L88) 키와 정확히 일치. 14개만 허용. |
| 4 | `label` | str (한글) | ✅ | 사람이 읽기 쉬운 라벨. 동일 field가 여러 행이면 괄호로 시나리오 구분. 예: `펀드명(공백/전각)`, `펀드명(약칭)` |
| 5 | `gold_label` | `match` \| `mismatch` \| `missing` | ✅ | 정답. §4.2 의미 정의 참조 |
| 6 | `mutation_type` | enum (§4.3) | ✅ | 정상도 어떤 "표기 차이 유형"인지 명시 |
| 7 | `difficulty` | `easy` \| `medium` \| `hard` | ✅ | 약한 모델 기준 난이도. §4.4 |
| 8 | `contract_raw` | str | 조건부 | 신탁계약서 원문. **고정 — 변조 금지**. missing(양쪽 누락) 시 빈 문자열 |
| 9 | `contract_page` | int \| 빈값 | 조건부 | 신탁계약서 PDF 1-based 페이지 |
| 10 | `im_raw` | str | 조건부 | IM 원문 또는 변조된 값. 누락 시 빈 문자열 |
| 11 | `im_page` | int \| 빈값 | 조건부 | IM PDF 1-based 페이지. 가짜 인용 테스트는 의도적으로 999 등 |
| 12 | `harness_signal` | enum (§4.5) | ✅ | 어느 모듈이 이 케이스를 잡아야 하는가(예측) |
| 13 | `weak_model_pitfall` | str | ✅ | 약한 로컬 모델이 실패할 것으로 예상되는 양상 한 줄 |
| 14 | `note` | str |  | 라벨러 메모, 단위 변환식, 출처 근거 등 |

### 빈 셀 규약

- 한쪽 누락(예: IM만 없음): 해당 쪽 `_raw`·`_page` 모두 빈 셀
- 양쪽 누락: 4개 컬럼(`contract_raw`, `contract_page`, `im_raw`, `im_page`) 모두 빈 셀
- 빈 셀은 절대 `null`·`None`·`-` 같은 문자열로 쓰지 않음 (단순 빈 문자열 `""`)

---

## 4. Enum 사전

### 4.1 `category`

| 값 | 의미 |
|---|---|
| `정상` | 신탁계약서·IM 원본 그대로(또는 표기 차이만 있음). gold_label은 `match` 또는 `missing` |
| `변조` | IM 값을 의도적으로 치환. gold_label은 항상 `mismatch` |

> **`category` 와 `gold_label` 매핑은 1:N 이 아님** — 정상은 match/missing 모두 가능하지만, 변조는 mismatch 만.

### 4.2 `gold_label`

| 값 | 의미 | 채점기 매핑 |
|---|---|---|
| `match` | 표기·단위 차이가 있어도 동일 사실 | [`FinalCheckStatus.EXACT_MATCH`](../src/pipelines/cross_check.py#L15-L20) 또는 `SAME_AFTER_NORMALIZATION` |
| `mismatch` | 사실이 다름. **재현율 측정의 positive 라벨** | `DIFFERENT_AFTER_NORMALIZATION` |
| `missing` | 한쪽/양쪽에 정보가 정당하게 부재 | `MISSING_EVIDENCE` |

> 재현율 = `mismatch`를 positive 로 보는 이진 분류. `missing`은 양성/음성에서 모두 제외(분모에서도 제외)해 정상 분류의 페널티가 안 가게 함.

### 4.3 `mutation_type`

정상에도 "표기 차이 유형"으로 사용 — 패턴 분석용.

#### 정상 (category=정상)
| 값 | 설명 | 예 |
|---|---|---|
| `whitespace_normalize` | 공백·전각·줄간격 차이만 | `제 1 호` vs `제1호` |
| `format_diff` | 표기 형식 차이(약칭·하이픈·괄호) | `2025년 7월 22일` vs `2025-07-22` |
| `unit_conversion` | 단위 환산 필요 | `1000분의 8.9` vs `0.89%` vs `89bp` |
| `ocr_typo` | OCR 노이즈 (1~2자 이내) | `이지스자산` vs `이지스지산` |
| `semantic_equivalent` | 표현이 다르나 의미 동일 | `환매 청구 불가` vs `폐쇄형` |
| `list_reorder` | 항목 순서·조사만 다름 | 집합 동치 |
| `missing_one_side` | 한쪽 결측이 정상 | IM에 명시 없음 |
| `missing_both` | 양쪽 결측이 정상 | 판매사 미정 |
| `missing_not_applicable` | 해당 없음(폐쇄형의 락업 등) | N/A |

#### 변조 (category=변조)
| 값 | 설명 | 어느 가드/모듈이 잡을 후보인가 |
|---|---|---|
| `digit_swap` | 자릿수는 같고 숫자만 교체 | cross_check |
| `decimal_shift` | 소수점 이동(가장 자주 빠지는 함정) | normalization+cross_check |
| `date_shift` | 일자/기간 변경 | llm_judge 또는 cross_check |
| `char_typo` | 1글자 치환 (OCR과 구분 필요) | cross_check+llm_judge |
| `entity_swap` | 회사명·인물명 완전 교체 | cross_check |
| `digit_insert` | 긴 문자열 중 1자리 추가 | cross_check |
| `bool_flip` | 부정/긍정 반전 | llm_judge |
| `invent_clause` | 계약서에 없는 조항을 IM이 환각 신설 | cross_check+llm_judge |
| `fake_citation` | 값은 정답이나 인용 페이지가 가짜 | **G2 출처 가드 전용** |
| `shacl_violation` | 값이 SHACL 범위 위반 (예: 보수 >5%) | **③ guard 조건에서 G3가 SHACL/제약 신호로 집행** |

> 신규 mutation_type 추가 시 PR로 본 문서를 함께 갱신 (enum 동기화).

### 4.4 `difficulty`

| 값 | 정의 (약한 로컬 모델 기준) |
|---|---|
| `easy` | 정규화 1회·문자열 비교로 판정 가능. 약한 모델도 ~80% 정답 |
| `medium` | 의미 동치·순서·OCR 등 추론 필요. 약한 모델 50~70% 정답 |
| `hard` | 단위 환산·날짜 산수·자릿수 함정·환각. 약한 모델 <40% 정답 |

> 난이도는 "**약한 로컬 모델 기준**"으로 매긴다. Opus 기준이 아니다. Opus는 hard도 대부분 잡는다 — 그래야 *우리 하네스가 왜 필요한가* 가 보인다.

### 4.5 `harness_signal`

어느 모듈이 이 케이스를 잡아야 하는지(예측). 채점 시 모듈별 효과 분리에 사용.

| 값 | 의미 |
|---|---|
| `normalization` | [`src/pipelines/normalize.py`](../src/pipelines/normalize.py) — 단위·표기 정규화 |
| `cross_check` | [`src/pipelines/cross_check.py`](../src/pipelines/cross_check.py) — 정규화 후 raw_text 비교 |
| `llm_judge` | [`src/pipelines/llm_judge.py`](../src/pipelines/llm_judge.py) — 의미 동등 판단 LLM |
| `g1_format` | 가드: 형식(JSON 스키마) 검사 |
| `g2_citation` | 가드: PDF 페이지 범위·실재 인용 검사 |
| `g3_constraint` | 가드: SHACL·숫자 범위·논리 신호를 reject/null 처리로 집행 |
| `shacl` | `pyshacl` 직접 호출. ② ontology 조건에서는 진단 산출물, ③ guard 조건에서는 G3 집행 신호 |
| `+` 연결 | 복수 모듈 협력 필요 (`normalization+cross_check`) |

---

## 5. 케이스 작성 규칙

### 5.1 일반 규칙 (정상·변조 공통)

1. `contract_raw` 는 PDF에서 그대로 따와야 함. 임의 요약·줄임 금지. 따옴표·괄호도 원문 유지.
2. `contract_page` 는 PDF 뷰어 표시 페이지(1-based). 표지를 1쪽으로 계산.
3. `field` 가 같은 케이스가 여러 개여도 됨 — 단, `label` 괄호로 시나리오를 구분(`펀드명(공백/전각)` vs `펀드명(약칭)`).
4. `note` 에 단위 환산식·근거 페이지·예외 사유를 짧게.

### 5.2 변조(category=변조) 규칙

| 규칙 | 사유 |
|---|---|
| **`contract_raw`·`contract_page` 는 절대 변경 금지** | 신탁계약서는 정답 기준. 스캔본 편집도 금지([ARCHITECTURE §2](./ARCHITECTURE.md)) |
| **`im_raw` 만 손치환** | 단일 변경점 → 변조 유형이 명확 |
| **변조 유형은 한 케이스당 1종** | 복합 변조 금지(채점기가 원인 분석 못함) |
| **`weak_model_pitfall` 필수** | 변조를 만든 이유 = 무엇을 시험하는가 |

### 5.3 합성 케이스 마킹

실제 IM 에 없는 시나리오(예: bp 표기·가짜 인용)는 `note` 에 **"합성 케이스 — IM 원본에 없음"** 를 명시. 리나가 PDF 검수할 때 건드리지 않도록.

현재 합성 케이스: **C002, C014, C029** (v0.1) + **C031, C033, C045, C046, C047, C052, C053, C054, C055, C058, C059, C060, C061, C062, C067, C069, C070, C075, C076, C077** (v0.2). PDF 원본에 없는 표기(전각·bp·콤마없는 천분율·가짜 인용 등)이거나 IM 원본에 없는 변형이므로 리나의 PDF 검수 대상에서 제외.

---

## 6. 워크플로

### 6.1 신규 케이스 추가
1. 다음 가용 `case_id` 부여 (현재 C081~)
2. `contract_raw` 는 PDF 원문 복사
3. PM 1차 검토 → `gold_label` 확정 → 머지

### 6.2 라벨링 v1 (W1~W2, 리나)
- 입력: `golden_master.csv` 양식 (PM 이 빈 시트 제공)
- 출력: `tests/golden/labeler_v1_rina.csv` (`case_id`, `gold_label` 만)
- 추측 라벨 금지. 모르면 `note` 에 질문 + 빈칸([Role_Dividing.md §1](./Role_Dividing.md))

### 6.3 κ 합의 (W2 끝)
1. 승훈도 별도로 라벨링 → `labeler_v2_pm.csv`
2. `mismatch` vs `not mismatch` 이진으로 Cohen's κ 계산
3. κ ≥ 0.7 → 토론 후 PM 최종 확정 → `golden_master.csv` freeze
4. κ < 0.7 → 가이드 보강 후 재라벨링

### 6.4 freeze 이후 변경
- 새 케이스 추가: PR + PM 승인 (기존 통계 영향 없음)
- 기존 케이스 수정: PR + 영향 분석(이미 발표한 통계가 바뀌는지) + PM 승인

---

## 7. 채점기 매핑 (참고)

```python
# src/scoring/scorer.py 가 따라야 할 매핑
FINAL_TO_PREDICTED = {
    "match":    {"exact_match", "same_after_normalization"},
    "mismatch": {"different_after_normalization"},
    "review":   {"needs_review"},
    "missing":  {"missing_evidence"},
}
```

> `needs_review` 는 불일치 확정이 아니라 "모르겠다/사람 검토 필요"로 분리한다. 가드가 reject 한 필드는 `missing_evidence` 로 null화되어도 가드가 문제를 확정적으로 잡은 것이므로 `mismatch` 예측으로 본다.

### 점수 정의

```
TP = (gold=mismatch) ∩ (pred=mismatch)
FP = (gold=match)    ∩ (pred=mismatch)
FN = (gold=mismatch) ∩ (pred=match | review | missing)
TN = (gold=match)    ∩ (pred=match)
REVIEW = (gold=match) ∩ (pred=review)
# missing 은 분모·분자 모두 제외

Precision = TP / (TP+FP)
Recall    = TP / (TP+FN)   ← 핵심 지표
F1        = 2PR / (P+R)
review_count = pred=review 전체 개수
review_rate  = review_count / 전체 케이스 수
```

---

## 8. 로딩 예시 (Python)

```python
import csv
from pathlib import Path

GOLDEN = Path("tests/golden/golden_master.csv")

with GOLDEN.open(encoding="utf-8-sig") as f:  # ← utf-8-sig 필수
    cases = list(csv.DictReader(f))

# 변조만 (재현율 분모)
mutations = [c for c in cases if c["category"] == "변조"]

# 가드 효과 측정용 — ②번에서 못 잡고 ③번에서만 잡는 케이스
guard_only = [c for c in cases
              if c["harness_signal"].startswith(("g2", "g3"))]

# 난이도별 분리
hard = [c for c in cases if c["difficulty"] == "hard"]
```

### pandas

```python
import pandas as pd
df = pd.read_csv(GOLDEN, encoding="utf-8-sig",
                 dtype={"contract_page": "Int64", "im_page": "Int64"})
# Int64 (대문자 I) — NA 허용 정수형
```

---

## 9. 현재 80케이스 구성

> v0.1 30케이스(C001~C030) + v0.2 50케이스(C031~C080, 빈자리 없이 연속). 모든 v0.2 케이스는 PM 확정본 `contract_raw` 만 재사용(출처 대조)하고, 수치/날짜/불리언/부재는 실제 하네스 `compare_values` 로 gold_label 정합성을 재계산해 검증함. 생성·검증 스크립트: [`scripts/expand_golden.py`](../scripts/expand_golden.py).

### 9.1 필드 커버리지

| field | 정상 | 변조 | 합 |
|---|--:|--:|--:|
| `fund.name` | 5 | 4 | 9 |
| `fund.type` | 2 | 3 | 5 |
| `fund.inception_date` | 5 | 4 | 9 |
| `fund.maturity_date` | 3 | 4 | 7 |
| `party.asset_manager` | 3 | 3 | 6 |
| `party.trustee` | 1 | 3 | 4 |
| `party.distributor` | 1 | 1 | 2 |
| `fee_schedule.management_fee` | 3 | 7 | 10 |
| `fee_schedule.trust_fee` | 3 | 4 | 7 |
| `fee_schedule.sales_fee` | 2 | 4 | 6 |
| `redemption_terms.is_redeemable` | 3 | 3 | 6 |
| `redemption_terms.lockup_period` | 1 | 1 | 2 |
| `redemption_terms.redemption_cycle` | 1 | 1 | 2 |
| `redemption_terms.redemption_fee` | 2 | 3 | 5 |
| **합** | **35** | **45** | **80** |

### 9.2 난이도 × 카테고리

| | easy | medium | hard | 합 |
|---|--:|--:|--:|--:|
| 정상 | 11 | 17 | 7 | 35 |
| 변조 | 0 | 14 | 31 | 45 |
| **합** | **11** | **31** | **38** | **80** |

### 9.3 harness_signal 분포

| signal | 케이스 수 |
|---|--:|
| `normalization` | 18 |
| `cross_check` | 18 |
| `llm_judge` | 22 |
| `normalization+cross_check` | 7 |
| `cross_check+llm_judge` | 7 |
| `g2_citation` | 5 |
| `g3_constraint+shacl` | 3 |

> 가드 전용 케이스: G2(가짜 인용) 5개 — `fund.name`(C029), `party.trustee`(C046), `fee_schedule.management_fee`(C075), `fund.inception_date`(C076), `redemption_terms.redemption_fee`(C062); G3/SHACL(범위 위반) 3개 — `management_fee`(C030, >5%), `trust_fee`(C052, >2%), `sales_fee`(C054, >3%). 모두 ②번 모드(진단)에서는 못 잡고 ③번 모드(집행)에서만 reject 되어야 가드 효과가 통계로 드러남(검증 완료).

### 9.4 라벨 논의 대기 케이스(일방 부재)

`party.distributor`(C047)·`lockup_period`(C058)·`redemption_cycle`(C059)는 계약서에 정당히 부재한 항목을 IM이 일방 신설한 경우다. 현재 하네스는 한쪽 결측을 `missing_evidence` 로 처리하므로 `mismatch` 로 자동 검출되지 않는다. gold_label=`mismatch`(권위 문서인 계약서에 없는 항목을 IM이 주장 = 불일치)는 **PM 최종 확정 필요**(§6.4). 현 하네스의 알려진 사각지대를 드러내는 케이스.

---

## 10. 자주 빠지는 함정 (FAQ)

**Q1. `case_id` 를 정리할 수 있나?**
A. 안 됨. 한 번 부여한 `case_id` 는 영구. 삭제된 케이스의 자리는 비워두고 다음 번호로.

**Q2. `contract_raw` 의 PDF 원문에 줄바꿈이 있으면?**
A. 공백 1개로 치환해 한 줄로 만들기. 원문 의미는 보존되지만 CSV 파싱 단순화.

**Q3. `im_page = 999` 처럼 명백히 가짜인 값은 어떻게 처리?**
A. `mutation_type=fake_citation` 인 변조 케이스에만 사용. 정상·다른 변조에서는 PDF 실제 페이지여야 함.

**Q4. SHACL 위반 케이스(C030)가 동작하려면?**
A. [`ontology/shapes.ttl`](../ontology/shapes.ttl) 의 `management_fee 0~5%` 제약이 ② `+온톨로지` 조건에서는 리포트로 남고, ③ `+가드` 조건에서는 G3가 같은 위반을 reject/null 처리한다. SHACL 위임을 끄면 G3의 Python 규칙만 적용된다.

**Q5. 변조 케이스의 `im_raw` 가 원문 그대로 보존되어야 할 이유는?**
A. 아니다 — 변조 케이스는 IM 값을 손치환하므로 `im_raw` 가 원문과 달라야 정상. 단 `contract_raw` 는 절대 보존([ARCHITECTURE §6](./ARCHITECTURE.md)).

**Q6. 라벨 합의가 안 되면?**
A. PM 이 최종 결정([Role_Dividing.md §1](./Role_Dividing.md)). 합의 불가 케이스는 `note` 에 양측 의견 기록 후 freeze.

---

## 변경 이력

| 버전 | 날짜 | 변경 | 작성 |
|---|---|---|---|
| v0.1 | 2026-05-29 | 초안 — 30케이스 + 14컬럼 스펙 확정 | 승훈 |
| v0.2 | 2026-06-06 | C031~C080 50케이스 추가(총 80). 출처 대조 + `compare_values` 자동 검증(`scripts/expand_golden.py`). 가드 커버리지 확장(G2 5·G3 3), 일방부재 라벨논의 케이스 3건 추가(§9.4). PM 확정/κ 합의 대기 | 승훈 |
