# Ontology Extraction PRD

> W1 기준 노종현 담당 온톨로지·추출 인터페이스 결정 문서.

## 목표

신탁계약서와 IM에서 MVP 핵심 4개념을 같은 구조로 추출한다. W1의 목적은 최종 판단이 아니라, 출처가 있는 원문 근거와 후보 정규화 값을 안정적으로 모으는 것이다.

## 범위

W1 입력 문서는 두 개로 고정한다.

- `신탁계약서`
- `IM`

핵심상품설명서는 W2 이후 필요성이 확인되면 확장한다.

## JSON 구조 원칙

추출 JSON은 문서별 묶음이 아니라 개념별 묶음 구조를 사용한다. 각 비교 항목 아래에 `contract`와 `im`을 나란히 둔다.

```json
{
  "schema_version": "v0",
  "fee_schedule": {
    "management_fee": {
      "contract": {
        "value": "0.7",
        "unit": "percent_per_year",
        "raw_text": "운용보수는 연 0.7%로 한다",
        "citation": {
          "document": "신탁계약서",
          "page": 12
        }
      },
      "im": {
        "value": "0.7",
        "unit": "percent_per_year",
        "raw_text": "운용보수 연 0.7%",
        "citation": {
          "document": "IM",
          "page": 8
        }
      }
    }
  }
}
```

## 값 단위 구조

각 문서 값은 아래 네 필드를 가진다.

| 필드 | 타입 | W1 의미 |
|------|------|---------|
| `value` | `string \| null` | LLM이 제안한 후보 정규화 값 |
| `unit` | `string \| null` | LLM이 제안한 후보 단위 |
| `raw_text` | `string \| null` | 원문에서 직접 가져온 근거 조각 |
| `citation` | `Citation \| null` | 문서 역할과 PDF 페이지 |

`value`와 `unit`은 W1 검증·비교용 확정값이 아니다. W2에서 정규화 규칙 테이블을 만들기 위한 후보 데이터로만 사용한다.

W1 추출 성공 여부는 `raw_text`와 `citation`으로 판단한다.

## Citation 규칙

```json
{
  "document": "신탁계약서",
  "page": 12
}
```

- `document` 허용값은 `신탁계약서`, `IM`뿐이다.
- `document`는 실제 파일명이 아니라 문서 역할명이다.
- `page`는 PDF 뷰어 기준 물리 페이지 번호다.
- `page`는 1부터 시작하는 정수다.
- `raw_text`가 있는데 `citation`이 없으면 신뢰 불가다.
- `citation.quote`는 두지 않는다. `raw_text`가 출처 검증 대상 근거 문장이다.

## 누락 표현

필드는 항상 존재해야 한다. 값을 못 찾은 경우 필드를 생략하지 않고 아래처럼 둔다.

```json
{
  "value": null,
  "unit": null,
  "raw_text": null,
  "citation": null
}
```

필드 누락은 schema guard 실패로 본다.

## W1 필드 목록

### Fund

- `fund.name`
- `fund.type`
- `fund.inception_date`
- `fund.maturity_date`

### Party

- `party.asset_manager`
- `party.trustee`
- `party.distributor`

W1에서는 운용사, 신탁업자, 판매사를 별도 RDF 개체로 분리하지 않는다. `Party` 하나의 개념 묶음 안에 속성으로 둔다.

### FeeSchedule

- `fee_schedule.management_fee`
- `fee_schedule.trust_fee`
- `fee_schedule.sales_fee`

환매수수료는 `fee_schedule`이 아니라 `redemption_terms.redemption_fee`에 둔다.

### RedemptionTerms

- `redemption_terms.is_redeemable`
- `redemption_terms.lockup_period`
- `redemption_terms.redemption_cycle`
- `redemption_terms.redemption_fee`

## W1 정규화 정책

W1 정규화는 추출 JSON을 덮어쓰지 않고 별도 산출물로 만든다.

- 산출 경로: `reports/manual_extract/normalization.json`
- 실행 옵션: `uv run python scripts/run_extract_once.py --normalize`
- 기존 추출 재사용: `uv run python scripts/run_extract_once.py --normalize --from-existing-extraction`

정규화 입력은 `raw_text`만 사용한다. `extraction.value`, `extraction.unit`,
`citation.page`는 AI 정규화 입력으로 넘기지 않는다. 단, 코드는 `raw_text`와
`citation.page`가 있는 side만 신뢰 가능한 정규화 대상으로 본다.

### W1 정규화 대상

우선 정규화 대상은 규칙과 비교 목적이 명확한 5개 필드로 제한한다.

- `fund.inception_date`
- `fund.maturity_date`
- `fee_schedule.management_fee`
- `fee_schedule.trust_fee`
- `fee_schedule.sales_fee`

그 외 W1 필드는 `normalization.json`에 포함하되 `status`를
`not_normalized`로 둔다.

### 상태값

필드 전체 `status`는 AI가 만들지 않고 코드가 계산한다.

- `same_after_normalization`: 양쪽 최종 정규화값과 단위가 같음
- `different_after_normalization`: 양쪽 정규화 성공, 값 또는 단위가 다름
- `partially_normalized`: 한쪽만 정규화 성공
- `normalization_failed`: 증거는 있으나 양쪽 모두 정규화 실패
- `not_normalized`: 정규화 대상이 아니거나 비교할 증거가 없음

각 객체는 `reason_code` 하나와 `reason` 하나를 가진다. `reason_code`는 기계
처리용이고, `reason`은 영어 설명이다.

주요 `reason_code`:

- `field_not_in_scope`
- `missing_evidence`
- `normalized_successfully`
- `normalization_failed`
- `same_normalized_value`
- `different_normalized_value`
- `partial_normalization_success`
- `reference_date_matched`
- `reference_date_single_side`
- `reference_date_conflict`
- `reference_date_missing`
- `derived_successfully`
- `derived_failed`

### AI 출력과 코드 후검증

정규화는 AI 기반으로 수행하되, AI 출력은 문자열 중심으로 제한한다. 코드는
필드별 허용 단위와 타입을 후검증하고 typed `normalized_value`를 만든다.

AI side 출력 예:

```json
{
  "normalized_text": "0.89",
  "normalized_unit": "percent_per_year",
  "raw_normalized_text": null,
  "raw_normalized_unit": null,
  "method": "direct",
  "reason_code": "normalized_successfully",
  "reason": "The annual fee was normalized to a percent value."
}
```

최종 side 결과 예:

```json
{
  "raw_text": "[운용] 연[ 0.89 ] %",
  "normalized_text": "0.89",
  "normalized_value": 0.89,
  "normalized_unit": "percent_per_year",
  "method": "direct",
  "reason_code": "normalized_successfully",
  "reason": "The annual fee was normalized to a percent value."
}
```

허용 단위와 타입:

- 보수율: `percent_per_year`, `normalized_value`는 number
- 날짜: `date`, `normalized_value`는 `YYYY-MM-DD` 문자열
- 기간 중간값: `month`, `raw_normalized_value`는 integer

AI가 허용 단위 밖의 값을 반환하거나, `normalized_text`에 단위를 포함해 코드
변환에 실패하면 해당 side는 `normalization_failed`로 본다. 보수율 숫자 비교는
절대 오차 `1e-6` 이하를 같은 값으로 본다.

### 파생 date 정규화

시작일 기반 파생 정규화는 모든 날짜/기간 필드에 허용하지 않는다. W1에서는
원래 의미가 종료 날짜인 `fund.maturity_date`에만 허용한다.

- `fund.inception_date`: 직접 `date` 정규화만 허용
- `fund.maturity_date`: 직접 날짜가 있으면 `direct`; 기간만 있으면
  `fund.inception_date`를 기준일로 사용해 `date` 파생 허용

파생 정규화가 있을 때만 중간값을 남긴다.

```json
{
  "raw_normalized_text": "24",
  "raw_normalized_value": 24,
  "raw_normalized_unit": "month",
  "normalized_text": "2027-07-22",
  "normalized_value": "2027-07-22",
  "normalized_unit": "date",
  "method": "derived_from_reference_date",
  "derived_from": ["fund.inception_date"]
}
```

기준일 정책:

1. 양쪽 `fund.inception_date`가 같은 날짜로 정규화되면 그 날짜를 사용한다.
2. 한쪽만 정규화됐고 해당 side에 `raw_text + citation.page`가 있으면 그 날짜를 사용한다.
3. 양쪽 날짜가 다르면 기준일을 사용하지 않는다.
4. 기준일을 사용한 경우 `reference_date`, `reference_date_field`,
   `reference_date_source`, `reference_date_policy`를 남긴다.

## TTL 식별자 규칙

TTL/Python/JSON 내부 식별자는 영어를 사용한다. 사람이 읽는 의미는 `rdfs:label`에 한국어로 둔다.

JSON 필드와 TTL 속성명은 모두 `snake_case`로 통일한다.

예:

```ttl
dnb:management_fee a rdf:Property ;
    rdfs:label "운용보수"@ko .
```

## JSON-TTL 매핑

| JSON field | TTL property |
|------------|--------------|
| `fund.name` | `dnb:fund_name` |
| `fund.type` | `dnb:fund_type` |
| `fund.inception_date` | `dnb:inception_date` |
| `fund.maturity_date` | `dnb:maturity_date` |
| `party.asset_manager` | `dnb:asset_manager` |
| `party.trustee` | `dnb:trustee` |
| `party.distributor` | `dnb:distributor` |
| `fee_schedule.management_fee` | `dnb:management_fee` |
| `fee_schedule.trust_fee` | `dnb:trust_fee` |
| `fee_schedule.sales_fee` | `dnb:sales_fee` |
| `redemption_terms.is_redeemable` | `dnb:is_redeemable` |
| `redemption_terms.lockup_period` | `dnb:lockup_period` |
| `redemption_terms.redemption_cycle` | `dnb:redemption_cycle` |
| `redemption_terms.redemption_fee` | `dnb:redemption_fee` |
