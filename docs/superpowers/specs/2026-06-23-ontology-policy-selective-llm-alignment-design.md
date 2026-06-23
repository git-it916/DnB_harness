# 온톨로지 정책 기반 선택적 LLM 하네스 정합화 설계

작성일: 2026-06-23

## 1. 목적

논문, 코드, 기준 문서에 섞여 있는 과거 실험 버전을 제거하고 최종 연구 주장을 하나로 통일한다.

최종 주장은 다음과 같다.

> 신탁계약서와 투자제안서의 정합성 검증에서, 온톨로지 기반 필드 정책으로 결정론적 비교를 우선 수행하고 해결되지 않은 의미 판단에만 LLM을 선택적으로 사용하는 Tier 2가 초기 정규화부터 판정까지 LLM을 폭넓게 사용하는 Tier 3보다 높은 F2-Score와 업무 효율성을 보였다.

이 설계에서 `ontology_policy_judge`를 제안 아키텍처로 정의한다.

## 2. 최종 연구 범위

### 2.1 데이터와 반복 조건

- 골든셋: v0.2, 총 80케이스
- 구성: 정상 35건, 불일치 45건
- 정당한 결측 4건은 분류 성능 계산에서 제외
- Tier별 반복: 30회
- Tier 2와 Tier 3의 LLM: `claude-sonnet-4-6`
- Tier 2와 Tier 3의 temperature: 0.7
- 주 지표: F2-Score
- 보조 지표: Efficiency Index
- 통계: Welch t-test, Mann-Whitney U, Tier 1 기준 일표본 t-test, Cohen's d

### 2.2 최종 3-Tier

| Tier | 식별자 | 역할 |
|---|---|---|
| Tier 1 | `ontology_policy` | 온톨로지 필드 정책과 결정론 파서만 적용한다. 미해결 항목은 `needs_review`로 남긴다. |
| Tier 2 | `ontology_policy_judge` | Tier 1을 우선 적용하고, 정책상 허용된 미해결 의미 판단에만 LLM Judge를 호출한다. 최종 제안 방식이다. |
| Tier 3 | `harness_norm_judge` | 원문 차이가 있는 평가 항목에 LLM 정규화를 폭넓게 적용하고, 남은 항목에 LLM Judge를 호출한다. Full-LLM 비교군이다. |

세 Tier에는 G1·G2·G3 가드를 공통 적용한다. 따라서 본 실험은 가드의 유무가 아니라 정합성 비교 단계에서 LLM을 어디까지 사용할 것인지를 비교한다.

## 3. “온톨로지 기반”의 정의

본 연구에서 온톨로지 기반이라는 표현은 RDF 파일을 생성했다는 사실만 의미하지 않는다. 다음 도메인 지식을 명시적으로 모델링하고 실행 가능한 정책으로 사용한다는 의미다.

1. `Fund`, `Party`, `FeeSchedule`, `RedemptionTerms`의 4개 개념
2. 개념에 속한 14개 핵심 필드
3. 필드별 값 유형
4. 필드별 canonicalizer
5. 필드별 비교 정책
6. 필드별 허용 범위
7. 필드별 결측 의미
8. 필드별 LLM Judge 허용 여부
9. 만기일처럼 다른 필드에서 값을 파생하는 관계

`ontology/field_policies.yaml`을 이 실행 가능한 온톨로지 정책의 단일 소스로 사용한다.

## 4. 계층별 역할

### 4.1 추출 스키마

Pydantic 스키마는 LLM 추출 결과를 4개 개념·14개 필드 구조로 제한한다. 각 문서 값은 `value`, `unit`, `raw_text`, `citation`을 가진다. 정합성 판정의 근거는 `raw_text`와 `citation`이다.

### 4.2 가드

- G1: JSON과 Pydantic 형식 검사
- G2: 문서 종류와 페이지 범위 검사
- G3: 보수 범위와 날짜 관계 등 결정론 제약 검사

가드는 위반값을 retry, reject, null 처리하는 집행 계층이다.

### 4.3 온톨로지 정책 비교

필드 정책과 결정론 파서는 백분율, 날짜, 기간, 불리언 등 기계적으로 해석 가능한 표현을 canonical value로 변환한다. 양쪽 canonical value가 결정적이면 코드로 일치 여부를 확정한다.

### 4.4 선택적 LLM Judge

결정론 정책이 결론을 내리지 못했고 해당 필드 정책이 Judge를 허용한 경우에만 호출한다. 펀드명 약칭, 엔티티명, 서술형 조건처럼 의미 수준 판단이 필요한 항목이 대상이다.

### 4.5 RDF/ABox와 SHACL

RDF/ABox는 추출된 `raw_text`를 계약서와 IM의 독립 인스턴스로 표현하여 추적 가능한 진단 산출물을 제공한다. SHACL은 문서 내부의 필수 구조, 개수, 범위, 날짜 관계를 진단한다.

RDF/ABox와 SHACL은 최종 3-Tier 성능 차이의 독립변수가 아니다. 따라서 논문에서는 다음처럼 제한해 주장한다.

- ABox: 감사 가능성과 구조화된 추적성
- SHACL: 문서 내부 구조와 업무 제약 진단
- 온톨로지 필드 정책: 문서 간 정합성 비교의 결정론적 기준
- 가드: 오류값 집행

SHACL 자체가 Tier 2의 성능 향상을 만들었다고 주장하지 않는다.

## 5. 최종 데이터 흐름

```text
골든셋 v0.2의 contract_raw / im_raw
  → Pydantic ExtractionResult 구성
  → 공통 G1/G2/G3 가드
  → 온톨로지 정책 기반 canonical comparison
  → Tier 1: 미해결 항목을 review로 유지
  → Tier 2: 미해결 항목만 선택적 LLM Judge
  → Tier 3: LLM normalization 후 LLM Judge
  → 골든 라벨과 비교
  → F2·EI 및 반복 분포 계산
  → 통계 검정
```

논문의 3-Tier 결과는 PDF 추출 단계의 정확도를 측정하지 않는다. 사전 구축된 골든셋 원문을 입력으로 사용하여 추출 이후 정합성 판정 아키텍처를 비교한다.

별도의 실제 PDF 실행 경로는 하네스의 작동 가능성과 산출물 생성을 검증하는 통합 경로로 유지하되, Table 4의 성능 수치와 혼동하지 않는다.

## 6. 코드 정합화 범위

### 6.1 단일 최종 실험 진입점

`scripts/run_30reps.py`와 `scripts/analyze_30reps.py`를 최종 재현 경로로 지정한다. 실행 결과는 Tier별 30개 `score.json`과 집계 `stats.json`이어야 한다.

### 6.2 실행 메타데이터

각 반복 결과에 다음 정보를 기록한다.

- golden version과 case count
- tier와 mode
- model
- temperature
- repetition number
- guard configuration
- ontology policy version 또는 파일 해시
- 실행 코드 commit SHA

### 6.3 ABox·SHACL 진단 연결

3-Tier 평가 경로에서도 가드 이후 대상 ExtractionResult를 ABox로 변환하고 SHACL 진단을 실행할 수 있게 한다. 이 결과는 진단 메타데이터로 기록하며 예측 라벨을 변경하지 않는다.

케이스별 평가가 13개 빈 필드를 가진 합성 ExtractionResult를 사용하므로, 전체 필수 구조 SHACL을 그대로 적용하면 무의미한 위반이 발생한다. 따라서 다음 중 하나를 구현 계획에서 선택한다.

- 평가 대상 필드에 해당하는 scoped SHACL 진단만 수행
- 80케이스 전체를 하나의 완전한 추출 결과로 조립한 후 별도 통합 진단 수행

기본 권고는 성능 평가와 SHACL 진단을 분리하여, Tier 점수에는 영향을 주지 않는 별도 통합 진단 산출물을 생성하는 것이다.

### 6.4 레거시 경로

다음은 삭제하지 않고 `legacy` 또는 archive 성격으로 명시한다.

- 30케이스 `baseline/ontology/guard`
- non-harness/harness/harness+norm 비교
- McNemar와 bootstrap 중심의 초기 실험

기본 CLI, README, STATUS, ARCHITECTURE 및 재현 runbook에서는 이 경로를 최종 결과로 소개하지 않는다.

## 7. 문서 정합화 범위

다음 문서를 80케이스 3-Tier 기준으로 갱신한다.

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/INTERFACES.md`
- `docs/GOLDENSET.md`
- `docs/ROADMAP.md`
- `docs/Role_Dividing.md`
- `docs/runbooks/reproduce-results.md`
- 발표 관련 현재 문서

과거 30케이스 지시와 결과는 `docs/archive/`에서만 역사 자료로 유지한다.

문서의 표준 용어는 다음과 같다.

| 용어 | 표준 의미 |
|---|---|
| 제안 아키텍처 | Tier 2 `ontology_policy_judge` |
| 결정론 기준선 | Tier 1 `ontology_policy` |
| Full-LLM 비교군 | Tier 3 `harness_norm_judge` |
| 온톨로지 정책 | `field_policies.yaml`과 canonical parser가 실행하는 필드 의미·비교 규칙 |
| RDF/ABox | 추적 가능한 구조화 진단 표현 |
| SHACL | 문서 내부 구조·제약 진단 |

## 8. 논문 수정 원칙

PDF 자체를 직접 편집하지 않는다. 우선 편집 가능한 원본 문서를 확보해 수정한 후 PDF를 다시 생성한다.

원본을 찾지 못하면 논문 내용을 Markdown 또는 Word 원고로 재구성하는 작업을 별도 범위로 진행한다.

논문에서 수정할 핵심 사항은 다음과 같다.

1. 연구 기여를 Tier 2의 온톨로지 정책 기반 선택적 LLM 구조로 명시
2. “SHACL이 성능을 높였다”는 인과 표현 제거
3. 3-Tier 결과가 추출 이후 판정 아키텍처를 비교한다는 사실 명시
4. Tier 1에는 LLM을 사용하지 않으며, Tier 2·3만 동일 모델을 사용한다고 정정
5. G1이 합성된 유효 JSON을 받기 때문에 형식 복구 효과는 본 실험에서 별도 측정되지 않았다고 한계에 명시
6. C030은 Python G3가 직접 차단하고 SHACL에도 동일 제약이 정의되어 있다고 정정
7. 결과표와 통계 수치는 현재 `database/gemma4_30reps/stats.json`을 단일 근거로 사용

## 9. 검증 기준

정합화 완료 조건은 다음과 같다.

- 모든 현재 기준 문서가 80케이스 3-Tier만 최종 실험으로 설명한다.
- 논문과 코드가 동일한 Tier 정의를 사용한다.
- 논문 수치가 `stats.json`에서 재생성 가능하다.
- Tier 2의 LLM 호출은 정책상 허용된 `needs_review`에만 발생한다.
- Tier 3은 LLM normalization과 Judge를 사용한다.
- 모든 Tier에 동일한 G1/G2/G3 설정이 적용된다.
- ABox·SHACL 산출물은 진단용이며 Tier 라벨을 변경하지 않는다.
- 전체 테스트가 프로젝트의 `uv run pytest` 환경에서 통과한다.

## 10. 비범위

- RDF/ABox 또는 SHACL 자체의 성능 향상을 증명하는 ablation 실험
- 새로운 펀드 데이터 추가
- 골든셋 라벨러 합의 완료
- G2의 실제 본문 문자열 존재 검증
- G3의 모든 금융 단위 변환 지원

이 항목들은 후속 연구 과제로 남긴다.
