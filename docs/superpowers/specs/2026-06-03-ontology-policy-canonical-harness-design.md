# 온톨로지 정책 기반 정규형 하네스 설계

## 목표

현재 30개 골든 케이스를 하드코딩하지 않으면서 기존 하네스를 개선하는 새로운 온톨로지 정책 기반 비교 경로를 추가한다.

현재 `harness+norm` 경로는 Claude 정규화와 judge 동작에 크게 의존한다. 새 경로는 1차 정규화와 비교를 필드 정책이 구동하는 결정론 코드로 옮긴다. LLM judge는 결정론적 canonicalization만으로 결론을 낼 수 없는 필드에 한해 fallback으로만 남긴다.

## 비목표

- 기존 `baseline`, `guard`, `harness+norm` 경로를 제거하거나 다시 작성하지 않는다.
- `case_id`, `golden_master.csv` 행, 전체 raw 문자열의 정확한 값, 페이지 번호, 현재 PDF 레이아웃에 맞춰 로직을 튜닝하지 않는다.
- 첫 번째 구현에서는 완전한 엔티티 alias 해소를 구현하지 않는다.
- 새 ontology-policy 경로에서 Claude 정규화를 사용하지 않는다.
- 이번 반복에서는 TTL/SHACL을 유일한 실행 가능한 정책 소스로 만들지 않는다.

## Source Of Truth

이 설계는 세 계층을 사용한다.

- `ontology/trust_fund.ttl`: 개념 모델.
- `ontology/shapes.ttl`: 구조 및 비즈니스 검증 규칙.
- `ontology/field_policies.yaml`: canonicalization, 비교, 부재 의미, judge fallback을 위한 실행 가능한 온톨로지 정책.

`field_policies.yaml`은 현재 `ExtractionResult`의 14개 필드로 제한한다. 다만 각 정책은 현재 리포트나 골든셋을 위한 규칙이 아니라 펀드/신탁 도메인 규칙으로 작성해야 한다.

## 새 모드

두 가지 score 모드를 추가한다.

- `ontology_policy`: 결정론 경로만 사용한다.
- `ontology_policy_judge`: 결정론 경로에 Claude judge fallback을 더한다.

`ontology_policy`는 빠르게 실행되어야 하며 외부 LLM 호출이 필요하지 않아야 한다. `ontology_policy_judge`는 최종 비교 모드이며, 정책상 허용되고 결정론 경로가 결론을 내지 못한 필드에 대해서만 judge를 호출한다.

## 파이프라인

`ontology_policy`:

```text
ExtractionResult
-> G1/G2/G3 guards
-> field policy lookup
-> canonicalization
-> deterministic comparison
-> decisive result or needs_review
-> score
```

`ontology_policy_judge`:

```text
ExtractionResult
-> G1/G2/G3 guards
-> field policy lookup
-> canonicalization
-> deterministic comparison
-> decisive result: final, no LLM call
-> non-decisive + judge_allowed=true: Claude judge fallback
-> non-decisive + judge_allowed=false: needs_review
-> score
```

결정론 canonical 결과가 확정한 판정은 LLM 출력으로 뒤집을 수 없다.

## Canonical 패키지

`src/canonical/`을 만든다.

- `types.py`: `FieldPolicy`, `CanonicalValue`, `CanonicalComparison`.
- `policy.py`: `ontology/field_policies.yaml` 로드 및 검증.
- `parsers.py`: percent, date, duration, boolean, absence를 위한 결정론 parser.
- `compare.py`: 정책 기반 비교.
- `pipeline.py`: `ExtractionResult`에서 `CrossCheckResult` 호환 출력으로 연결하는 bridge.

canonical 계층은 PDF에서 값을 추출하지 않는다. 이미 추출된 evidence를 해석하기만 한다.

## 필드 정책

14개 필드를 모두 등록한다. 각 정책에는 다음이 포함된다.

- `label`
- `value_type`
- `canonicalizer`
- `compare_policy`
- `judge_allowed`
- `absence_semantics`
- 선택적 range 또는 derivation 설정

첫 번째 구현의 canonicalizer:

- Percent 필드: 운용보수, 신탁보수, 판매보수, 환매수수료.
- Date 필드: 설정일, 만기일.
- Duration 필드: 락업 기간, 그리고 설정일에 명시적으로 묶인 만기일 derivation.
- Boolean 필드: 환매 가능 여부.
- Absence semantics: "없음", "해당 없음", "부과하지 아니함" 및 유사 표현의 필드별 처리.

첫 번째 구현의 judge fallback 필드:

- `fund.name`
- `fund.type`
- `party.asset_manager`
- `party.trustee`
- `party.distributor`
- `redemption_terms.redemption_cycle`

이 필드들은 raw exact match만으로 충분하지 않을 때 정책에 따라 judge fallback으로 라우팅한다. 이번 반복에서는 완전한 canonicalization을 하지 않는다.

## Percent 정책

결정론 percent canonicalization은 명시적 단위만 허용한다.

- `%`
- `bp` / basis point
- `1,000분의`, `1000분의`, `1천분의`

`0.0089`처럼 단위 없는 decimal 값은 결정론 코드가 해석하지 않는다. 이런 값은 non-decisive로 남기고, 필드 정책이 허용할 때만 judge fallback으로 보낼 수 있다.

이 정책은 단위 없는 숫자를 안전하다고 가장하지 않으면서도, IM 형식 전반에서 명시적 도메인 단위를 견고하게 처리하기 위한 것이다.

## Date 및 Duration 정책

ISO, 점 구분 날짜, 슬래시 구분 날짜, 한국어 날짜 표현으로 쓰인 절대 날짜는 canonicalize한다.

`lockup_period`는 `3년`, `36개월` 같은 독립 duration을 canonicalize한다.

`fund.maturity_date`는 raw text가 설정일을 명시적으로 참조할 때만 derived date를 지원한다. 예시는 다음과 같다.

- `설정일로부터 3년`
- `최초설정일로부터 36개월`

Derivation에는 같은 side의 `fund.inception_date`를 사용한다.

- contract maturity는 contract inception을 사용한다.
- IM maturity는 IM inception을 사용한다.

`3년`, `36개월`처럼 독립적으로 쓰인 maturity 값은 non-decisive로 남기고, 허용된 경우 judge fallback을 사용한다.

## Absence Semantics

부재 의미는 필드별이다.

- 일부 fee 필드는 "없음", "해당 없음", "부과하지 아니함" 또는 유사 표현을 zero value로 해석할 수 있다.
- 필수 entity/name 필드는 부재 표현을 missing evidence로 해석한다.
- Boolean 필드는 정책이 명시적으로 허용할 때 absence-like 또는 negative 표현을 false로 매핑할 수 있다.

따라서 같은 raw phrase라도 field policy에 따라 서로 다른 canonical 의미를 만들 수 있다.

## CrossCheckResult 확장

기존 `CrossCheckResult` 필드를 유지하고, 선택적 canonical evidence를 추가한다.

- `canonical_status`
- `canonical_reason_code`
- `canonical`

기존 scoring은 계속 `final_status`와 `guard_rejections`를 사용한다. canonical 필드는 기계 판독 가능한 설명과 디버깅 evidence를 제공한다.

## 과적합 방지 원칙

구현은 다음을 해서는 안 된다.

- `case_id`로 분기하지 않는다.
- `golden_master.csv` 행을 로직으로 읽거나 인코딩하지 않는다.
- 현재 리포트의 전체 raw 문자열을 정확히 매칭하지 않는다.
- 현재 페이지 번호, 현재 PDF 파일명, 현재 표 위치를 policy로 사용하지 않는다.
- C021, C030 또는 어떤 골든 케이스 이름을 딴 규칙을 추가하지 않는다.

구현은 다음을 해도 된다.

- percent, permille, basis point, date, duration, boolean, absence phrase 같은 일반 표현군을 파싱한다.
- `field_policies.yaml`의 필드 의미를 사용한다.
- value type, range, requiredness, comparison policy 같은 도메인 수준 제약을 사용한다.

`golden_master.csv`는 최종 scoring 입력이지 튜닝 소스가 아니다.

## 검증

다음에 대한 focused test를 추가한다.

- Field policy 로딩 및 14개 필드 전체 coverage.
- Percent parser 표현군.
- Date 및 duration parser 표현군.
- 필드별 absence semantics.
- Canonical comparison의 decisive 및 non-decisive 동작.
- Decisive canonical result에 judge를 호출하지 않는 judge fallback 라우팅.
- 기존 scoring 호환성.

실행:

```bash
python -m pytest -q
python -m src.cli score --mode ontology_policy --out reports/scoring/score_ontology_policy.json
python scripts/score_ontology_policy.py
```

최종 비교에는 기존 모드에 더해 다음 모드가 포함되어야 한다.

- `ontology_policy`
- `ontology_policy_judge`

현재 잠정 골든셋 기준 목표:

- `ontology_policy_judge` F1 >= 현재 `harness+norm` F1.
- Recall >= 현재 `harness+norm` recall.
- 단위 함정 false negative는 case-specific logic이 아니라 일반 explicit-unit parsing으로 제거한다.
- Claude judge 호출 수는 현재 `harness+norm`보다 적다.
