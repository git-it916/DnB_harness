# W1 온톨로지 연결 파이프라인

이 문서는 W1에서 건이 맡은 **추출/가드 결과와 온톨로지 검증을 연결하는 코드 파이프라인**을 설명한다.

## 목표

가드가 끝난 LLM 추출 결과를 온톨로지에서 읽을 수 있는 RDF ABox로 바꾸고, 그 ABox가 W1 검증 규칙을 만족하는지 검사한다.

```text
extraction_after_guards.json
+ normalization.json
        ↓
mapping.py
        ↓
abox.ttl
        ↓
validate.py
        ↓
shacl_validation.json
```

## 입력 파일

- `reports/run_A/extraction_after_guards.json`
  - G1/G2/G3 가드를 지난 LLM 추출 결과
  - 원본 `value`, `unit`, `raw_text`, `citation`을 보존한다.
- `reports/run_A/normalization.json`
  - 계약서와 IM 값을 같은 형식으로 비교할 수 있게 정규화한 결과
  - `normalized_value`, `normalized_unit`을 제공한다.

## 출력 파일

- `reports/run_A/abox.ttl`
  - 계약서 쪽 인스턴스와 IM 쪽 인스턴스를 모두 담은 RDF ABox
- `reports/run_A/shacl_validation.json`
  - W1 온톨로지 규칙 검증 결과

## 실행 명령

```powershell
python -m dnb_harness.ontology.mapping `
  --extraction reports/run_A/extraction_after_guards.json `
  --normalization reports/run_A/normalization.json `
  --output reports/run_A/abox.ttl
```

```powershell
python -m dnb_harness.ontology.validate `
  --data reports/run_A/abox.ttl `
  --shapes ontology/shapes.ttl `
  --output reports/run_A/shacl_validation.json
```

## 구현 결정

`mapping.py` 안에서 정규화를 새로 수행하지 않는다.

대신 두 파일을 합친다.

- `extraction_after_guards.json`: 원본 추출값, 원문 근거, 출처 페이지
- `normalization.json`: 검증과 비교에 쓸 정규화 값

이렇게 분리하면 각 단계의 책임이 명확하다.

```text
추출 = extractor
가드 = guards
정규화 = normalization
온톨로지 연결 = mapping.py
검증 = validate.py
```

## ABox에 들어가는 정보

각 필드마다 가능한 경우 아래 정보를 모두 넣는다.

```text
value
unit
raw_text
citation.document
citation.page
normalized_value
normalized_unit
```

예를 들어 운용보수는 다음처럼 저장된다.

```ttl
data:fee_schedule_contract a dnb:FeeSchedule ;
  dnb:management_fee_value "1000분의 8.9" ;
  dnb:management_fee_unit "permille_per_year" ;
  dnb:management_fee_raw_text "집합투자업자보수율 : 연 1,000분의 8.9" ;
  dnb:management_fee_document "신탁계약서" ;
  dnb:management_fee_page "15"^^xsd:integer ;
  dnb:management_fee_normalized_value "0.89"^^xsd:decimal ;
  dnb:management_fee_normalized_unit "percent_per_year" .
```

## 검증 방식

`validate.py`는 기본적으로 **SHACL 검증(`pyshacl`)을 필수로 사용한다.**

따라서 실행 환경에 아래 패키지가 설치되어 있어야 한다.

```powershell
pip install pyshacl rdflib
```

검증 실행 명령은 다음과 같다.

```powershell
python -m dnb_harness.ontology.validate `
  --data reports/run_A/abox.ttl `
  --shapes ontology/shapes.ttl `
  --output reports/run_A/shacl_validation.json
```

개발 환경에서 `pyshacl`이 아직 없을 때만 임시로 fallback 검증을 사용할 수 있다.

```powershell
python -m dnb_harness.ontology.validate `
  --data reports/run_A/abox.ttl `
  --shapes ontology/shapes.ttl `
  --output reports/run_A/shacl_validation.json `
  --allow-fallback
```

단, 발표/최종 실험에서는 fallback이 아니라 SHACL 검증 결과를 사용한다.

W1 fallback 검증 규칙은 다음과 같다.

- 운용보수: 0% 이상 5% 이하
- 신탁보수: 0% 이상 2% 이하
- 판매보수: 0% 이상 3% 이하
- 만기일이 설정일보다 늦어야 함

## W1에서 건이 설명할 한 문장

> 가드가 끝난 추출 JSON과 정규화 결과를 합쳐 RDF ABox를 만들고, 그 ABox를 SHACL 규칙으로 검증해 온톨로지 연결부를 재현 가능하게 만들었다.
