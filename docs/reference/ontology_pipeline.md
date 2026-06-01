# Ontology Pipeline Overview

> 현재 레포에서 신탁계약서와 IM을 읽어 온톨로지 기반 비교 하네스까지 가져가는 전체 흐름 정리.

## 한 줄 요약

현재 파이프라인은 PDF 두 개를 LLM으로 구조화 추출하고, 추출 결과를 스키마로 검증한 뒤, raw text 기반 교차검증과 AI 정규화를 수행한다. 추출 JSON은 RDF 그래프로 매핑할 수 있고, RDF 그래프는 TTL 온톨로지와 SHACL shape로 최소 구조 검증을 받는다.

3조건 실험에서는 이 온톨로지 파이프라인을 ② `+온톨로지` 조건의 진단 산출물로 사용한다. SHACL 위반은 여기서 결과를 수정하지 않고 리포트로만 남긴다. ③ `+가드` 조건에서는 G3가 같은 Python 제약/SHACL 신호를 reject/null 처리로 집행한다.

```text
신탁계약서 PDF + IM PDF
  -> LLM extraction
  -> extraction.json
  -> raw_text cross_check
  -> cross_check.json
  -> optional LLM judge
  -> llm_judgements.json
  -> optional AI normalization
  -> normalization.json
  -> normalization-aware cross_check final_status
  -> RDF/ABox mapping
  -> abox.ttl
  -> SHACL validation
  -> shacl_report.txt / shacl_validation.json
```

## 현재 W1 범위

입력 문서는 W1에서 두 개로 고정한다.

- `신탁계약서`
- `IM`

비교 필드는 14개다.

- `fund.name`
- `fund.type`
- `fund.inception_date`
- `fund.maturity_date`
- `party.asset_manager`
- `party.trustee`
- `party.distributor`
- `fee_schedule.management_fee`
- `fee_schedule.trust_fee`
- `fee_schedule.sales_fee`
- `redemption_terms.is_redeemable`
- `redemption_terms.lockup_period`
- `redemption_terms.redemption_cycle`
- `redemption_terms.redemption_fee`

W1 온톨로지 개념은 4개다.

- `Fund`
- `Party`
- `FeeSchedule`
- `RedemptionTerms`

## 1. LLM Extraction

실행 진입점은 `scripts/run_extract_once.py`다.

```bash
uv run python scripts/run_extract_once.py
```

기본 입력 PDF:

- `database/제정신탁계약서_날인본_이지스블랙ON1호_20250722_최종버전.pdf`
- `database/이지스 블랙ON 1호_준감필.pdf`

주요 코드:

- `src/pipelines/extract.py`
- `src/client/anthropic_client.py`
- `prompts/v0/extract/system.md`
- `src/schemas/extraction.py`

흐름:

1. `DocumentInput(role, path)`로 신탁계약서와 IM을 받는다.
2. PDF를 base64 document block으로 Anthropic API에 전달한다.
3. LLM은 `prompts/v0/extract/system.md` 규칙에 따라 JSON만 반환해야 한다.
4. 반환 JSON은 `ExtractionResult` Pydantic 스키마로 검증된다.
5. 결과는 `reports/manual_extract/extraction.json`에 저장된다.

추출 JSON의 핵심 원칙:

- 문서별 구조가 아니라 개념별 구조다.
- 각 비교 필드 아래에 `contract`, `im`을 나란히 둔다.
- `value`, `unit`은 LLM 후보값이다.
- W1에서 신뢰하는 근거는 `raw_text`와 `citation`이다.
- `raw_text`가 있으면 `citation.document`, `citation.page`가 있어야 한다.
- `quote`, `confidence`는 사용하지 않는다.

예:

```json
{
  "fee_schedule": {
    "management_fee": {
      "contract": {
        "value": "연 1000분의 8.9",
        "unit": "percent_per_year",
        "raw_text": "집합투자업자보수율 : 연 1,000 분의 8.9",
        "citation": {
          "document": "신탁계약서",
          "page": 15
        }
      },
      "im": {
        "value": "연 0.89%",
        "unit": "percent_per_year",
        "raw_text": "[운용] 연[ 0.89 ] %",
        "citation": {
          "document": "IM",
          "page": 9
        }
      }
    }
  }
}
```

## 2. Raw Text Cross Check

추출이 끝나면 항상 deterministic cross check를 수행한다.

주요 코드:

- `src/pipelines/cross_check.py`

산출물:

- `reports/manual_extract/cross_check.json`

cross check는 `value/unit`을 사용하지 않는다. 오직 양쪽 `raw_text` 존재 여부와 공백 정규화된 raw text만 본다.

상태값:

- `exact_match`: 양쪽 raw text가 공백 정규화 후 완전히 같음
- `needs_review`: 양쪽 raw text는 있지만 서로 다름
- `missing_evidence`: 한쪽 또는 양쪽 raw text가 없음

결측 방향:

- `contract`
- `im`
- `both`
- `none`

현재 성격상 대부분의 필드는 원문 표현이 달라 `needs_review`가 된다. 이것은 실패가 아니라 의도된 1차 분류다.

`--normalize`가 같이 실행되면 `cross_check.json`에는 raw text 기준 `status`와 정규화 반영 `final_status`가 함께 들어간다.

- `status`: raw text 기준 1차 판정
- `normalization_status`: 해당 필드의 정규화 결과 상태
- `final_status`: raw 판정에 정규화 결과를 반영한 최종 판정
- `final_reason_code`: 최종 판정 사유 코드
- `final_reason`: 최종 판정 설명

정규화가 결정적인 결과를 주는 경우:

- `same_after_normalization`: raw text는 다르지만 정규화값과 단위가 같음
- `different_after_normalization`: raw text는 다르고 정규화값 또는 단위도 다름

raw evidence가 없는 `missing_evidence`는 normalization이 있어도 최종 판정을 덮어쓰지 않는다.

## 3. Optional LLM Judge

`needs_review`인 필드만 LLM judge에 넘긴다.

실행:

```bash
uv run python scripts/run_extract_once.py --judge
```

주요 코드:

- `src/pipelines/llm_judge.py`
- `prompts/v0/judge/system.md`

산출물:

- `reports/manual_extract/llm_judgements.json`

judge 입력:

- `field`
- `label`
- `contract_raw_text`
- `im_raw_text`

judge에 넘기지 않는 것:

- `citation`
- `page`
- PDF 원문 전체
- `value/unit`

judge 출력:

- `reason`
- `status`

허용 status:

- `same`
- `different`

judge는 보수적으로 동작해야 한다. 같은 의미라고 확신할 수 없으면 `different`로 보는 방향이다.

정규화가 적용된 실행에서는 `final_status`가 `needs_review`인 필드만 judge 대상이 된다. 예를 들어 보수율과 날짜가 `same_after_normalization`으로 해결되면 judge 호출 대상에서 제외된다.

## 4. Optional AI Normalization

정규화는 별도 옵션으로 실행한다.

```bash
uv run python scripts/run_extract_once.py --normalize
```

기존 추출 결과를 재사용해 정규화만 다시 실험할 수 있다.

```bash
uv run python scripts/run_extract_once.py --normalize --from-existing-extraction
```

주요 코드:

- `src/pipelines/normalize.py`
- `prompts/v0/normalize/system.md`

산출물:

- `reports/manual_extract/normalization.json`

정규화 목적:

- raw text 표현 차이를 비교 가능한 값으로 맞춘다.
- 나중에 cross check가 normalized value/unit을 근거로 자동 매칭할 수 있게 한다.
- extraction의 `value/unit`은 사용하지 않는다.

W1 정규화 대상:

- `fund.inception_date`
- `fund.maturity_date`
- `fee_schedule.management_fee`
- `fee_schedule.trust_fee`
- `fee_schedule.sales_fee`

그 외 9개 필드는 `normalization.json`에 포함하되 `not_normalized`로 둔다.

정규화 방식:

1. AI가 field 단위로 contract/im raw text를 같이 받는다.
2. AI는 `normalized_text`를 문자열로만 반환한다.
3. AI는 단위를 `normalized_unit`에만 반환한다.
4. 코드는 허용 단위와 타입을 후검증한다.
5. 코드는 typed `normalized_value`를 만든다.
6. field-level `status`는 AI가 아니라 코드가 계산한다.

AI 출력 예:

```json
{
  "normalized_text": "0.89",
  "normalized_unit": "percent_per_year",
  "method": "direct",
  "reason_code": "normalized_successfully",
  "reason": "The annual fee was normalized to a percent value."
}
```

코드 후처리 후:

```json
{
  "normalized_text": "0.89",
  "normalized_value": 0.89,
  "normalized_unit": "percent_per_year",
  "method": "direct"
}
```

정규화 status:

- `same_after_normalization`
- `different_after_normalization`
- `partially_normalized`
- `normalization_failed`
- `not_normalized`

허용 단위와 타입:

- `percent_per_year`: number
- `date`: `YYYY-MM-DD` string
- `month`: integer, 파생 정규화 중간값에 사용

보수율 비교는 절대 오차 `1e-6` 이하를 같은 값으로 본다.

## 5. Derived Date Normalization

파생 date 정규화는 모든 날짜/기간 필드에 허용하지 않는다. W1에서는 원래 의미가 종료 날짜인 `fund.maturity_date`에만 허용한다.

예:

```text
fund.inception_date = 2025-07-22
fund.maturity_date contract = 2027년 7월 22일
fund.maturity_date im = 2년
```

정규화 결과:

```json
{
  "raw_normalized_text": "24",
  "raw_normalized_value": 24,
  "raw_normalized_unit": "month",
  "normalized_text": "2027-07-22",
  "normalized_value": "2027-07-22",
  "normalized_unit": "date",
  "method": "derived_from_reference_date",
  "derived_from": ["fund.inception_date"],
  "reference_date": "2025-07-22",
  "reference_date_source": "both",
  "reference_date_policy": "both_sides_same"
}
```

기준일 정책:

1. 양쪽 `fund.inception_date`가 같은 날짜로 정규화되면 그 날짜를 사용한다.
2. 한쪽만 정규화됐고 해당 side에 `raw_text + citation.page`가 있으면 그 날짜를 사용한다.
3. 양쪽 날짜가 다르면 기준일을 사용하지 않는다.
4. 기준일을 사용한 경우 `reference_date`, `reference_date_field`, `reference_date_source`, `reference_date_policy`를 남긴다.

## 6. RDF/ABox Mapping

추출 JSON은 RDF 그래프로 변환할 수 있다.

주요 코드:

- `src/ontology/mapping.py`

온톨로지 파일:

- `ontology/trust_fund.ttl`

매핑 원칙:

- RDF에는 `raw_text`만 넣는다.
- `value/unit/citation`은 RDF에 넣지 않는다.
- contract와 im은 별도 document-scoped node로 분리한다.
- raw text가 `null`인 필드는 RDF triple을 만들지 않는다.

생성되는 주요 node:

- `data:fund_contract`
- `data:fund_im`
- `data:party_contract`
- `data:party_im`
- `data:fee_schedule_contract`
- `data:fee_schedule_im`
- `data:redemption_terms_contract`
- `data:redemption_terms_im`

예:

```text
ExtractionResult
  -> data:fund_contract a dnb:Fund
  -> data:fund_im a dnb:Fund
  -> data:fund_contract dnb:has_fee_schedule data:fee_schedule_contract
  -> data:fee_schedule_contract dnb:management_fee "<raw_text>"
```

## 7. SHACL Validation

RDF 그래프는 SHACL로 최소 구조 검증을 받을 수 있다.

주요 코드:

- `src/ontology/validate.py`

shape 파일:

- `ontology/shapes.ttl`

W1 SHACL은 최소 필수 구조만 본다.

`Fund`:

- `fund_name`
- `has_party`
- `has_fee_schedule`
- `has_redemption_terms`

`Party`:

- `party_contract`: `asset_manager`, `trustee`
- `party_im`: `asset_manager`

`FeeSchedule`:

- `management_fee`

IM에는 신탁업자 역할 표시만 있고 회사명이 없는 경우가 있으므로, W1에서는 `party_im.trustee`를 필수로 강제하지 않는다. 신탁계약서 쪽 `party_contract.trustee`는 필수다.

SHACL은 현재 “문서 간 값이 같은가”를 판단하지 않는다. 그 역할은 cross check, judge, normalization 쪽에 있다. 또한 ② `+온톨로지` 조건에서 SHACL은 진단 산출물일 뿐 추출 결과를 고치지 않는다. 추출 결과를 reject/null 처리하는 집행은 ③ `+가드` 조건의 G3 책임이다.

## 8. 현재 산출물 구조

기본 출력 폴더:

```text
reports/manual_extract/
```

주요 파일:

- `extraction.json`: LLM 추출 원본 구조화 결과
- `cross_check.json`: raw text 기반 deterministic 비교
- `llm_judgements.json`: `needs_review` 필드에 대한 optional judge 결과
- `normalization.json`: optional AI normalization 결과
- `abox.ttl`: extraction raw text를 RDF/ABox로 매핑한 그래프
- `shacl_report.txt`: SHACL validation 사람이 읽는 리포트
- `shacl_validation.json`: SHACL validation machine-readable 요약
- `extraction_error.txt`: extraction 실패 시 오류 메시지

현재 예시 실행 결과 기준:

- `normalization.json`에서 정규화 대상 5개는 모두 `same_after_normalization`
- 나머지 9개는 `not_normalized`
- `fund.maturity_date`는 IM의 `2년`을 `fund.inception_date` 기준으로 `2027-07-22`로 파생 정규화
- `cross_check.json`의 `final_status` 기준으로 `same_after_normalization` 5개, `needs_review` 5개, `missing_evidence` 4개가 나온다.
- `shacl_validation.json`은 `conforms: true`다.

## 9. 실행 명령어

새 extraction 실행:

```bash
uv run python scripts/run_extract_once.py
```

새 extraction + judge:

```bash
uv run python scripts/run_extract_once.py --judge
```

새 extraction + normalization:

```bash
uv run python scripts/run_extract_once.py --normalize
```

기존 extraction 재사용 + normalization:

```bash
uv run python scripts/run_extract_once.py --normalize --from-existing-extraction
```

기존 extraction 재사용 + normalization + judge:

```bash
uv run python scripts/run_extract_once.py --normalize --judge --from-existing-extraction
```

온톨로지 산출물을 생략하고 싶을 때:

```bash
uv run python scripts/run_extract_once.py --skip-ontology
```

테스트:

```bash
uv run pytest
```

## 10. 현재까지 구현된 것과 남은 연결

구현된 것:

- PDF 기반 extraction
- extraction schema guard
- raw text/citation evidence guard
- raw text cross check
- optional LLM judge
- optional AI normalization
- normalization 후검증과 typed value 생성
- normalization-aware cross check final status
- RDF/ABox mapping
- CLI RDF/ABox output: `abox.ttl`
- SHACL validation wrapper
- CLI SHACL output: `shacl_report.txt`, `shacl_validation.json`
- W1 TTL ontology
- W1 SHACL shapes

아직 다음 단계로 연결할 것:

- 가드 팀 작업과 합쳐 full harness 결과 리포트 생성
- 골든셋 채점기와 통계 실험 파이프라인 연결

## 11. 현재 신뢰 경계

현재 시스템에서 신뢰 경계는 이렇게 나뉜다.

- `extraction.value/unit`: LLM 후보값, 직접 비교 근거 아님
- `extraction.raw_text + citation.page`: W1 추출 근거
- `cross_check.status`: raw text 기준 1차 deterministic 분류
- `cross_check.final_status`: normalization이 있으면 이를 반영한 현재 최종 비교 판정
- `llm_judgements.status`: needs_review에 대한 보조 의미 판단
- `normalization.normalized_value/unit`: 후검증을 통과한 비교 후보값
- RDF graph: raw text 기반 온톨로지 구조 표현
- SHACL result: RDF 구조가 최소 필수 조건을 만족하는지에 대한 검증. ②에서는 진단, ③에서는 G3 집행 신호로 사용 가능

따라서 현재 단계에서 날짜·보수율 필드는 `final_status`로 자동 매칭까지 가능하고, RDF/ABox 및 SHACL 산출물도 한 번의 CLI 실행으로 생성된다. 다음 작업은 가드·골든셋 채점기와 합쳐 full harness 리포트로 만들고, ③ 조건에서만 G3가 규칙 위반을 집행하도록 연결하는 것이다.
