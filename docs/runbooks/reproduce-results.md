# Reproduce Results Runbook — 채점 · 통계 · 라이브 하네스

## 목적

`src/scoring` · `src/cli` · `src/harness` · `src/stats` 가 만들어진 뒤 **지금까지 나온 결과를 그대로 재현**하는 절차. 결정적(LLM 불필요) 채점부터 실제 Ollama 라이브 풀런까지 한 줄씩 기록한다.

> 상태 변화는 `docs/STATUS.md`, 스키마는 `docs/INTERFACES.md`, 정답 매핑은 `docs/GOLDENSET.md §7`이 단일 진실 소스다. 이 문서는 *실행 절차*만 다룬다.

## 0. 환경

- conda env **`dnb_harness`** 사용 (Python 3.11). **`uv run` 금지.**
- 이 문서의 `python` 은 모두 그 env 의 인터프리터다.

```bash
conda activate dnb_harness
# Windows 한글 출력 깨짐 방지
set PYTHONIOENCODING=utf-8        # PowerShell: $env:PYTHONIOENCODING="utf-8"
```

검증:

```bash
python -m pytest -q          # 전체 회귀 (현재 81 passed)
```

## 1. 결정적 채점 (LLM 불필요)

골든 30케이스의 raw_text 를 하네스 로직(cross_check, +가드)에 통과시켜 `score.json` 산출. Ollama 없이 즉시 실행된다.

```bash
python -m src.cli score --mode ontology --out reports/scoring/score_ontology.json
python -m src.cli score --mode guard    --out reports/scoring/score_guard.json
```

실측 출력(`needs_review`를 `review`로 분리한 현재 채점 기준):

```
[ontology] P=0.000 R=0.000 F1=0.000 모르겠다=26 환각=0.000  ->  reports/scoring/score_ontology.json
[guard]    P=1.000 R=0.167 F1=0.286 모르겠다=24 환각=0.000  ->  reports/scoring/score_guard.json
```

- `--contract-pages` / `--im-pages` 는 G2 출처 범위 기준(기본 22 / 32, 실제 PDF 페이지 수).
- `by_signal` 에서 `g2_citation` · `g3_constraint+shacl` 의 `hit_rate=1.0` → C029(가짜 인용)·C030(SHACL 위반)을 가드가 정확히 잡는다.

> **해석:** `needs_review`는 더 이상 mismatch 확정이 아니라 `review`(모르겠다)로 분리한다. 따라서 ontology/guard 단독은 자동 확정이 적고 review 큐가 크다. 정규화·canonical policy·judge 단계는 이 review를 줄여 자동 확정 범위를 늘리는 역할이다.

## 2. 비교 리포트

```bash
python -m src.cli compare \
  reports/scoring/score_ontology.json reports/scoring/score_guard.json \
  --out reports/compare_det.md --model gemma4:31b
```

→ `reports/compare_det.md` 에 핵심 지표표 + 난이도별 Recall 표 생성 (통계 칸은 §4 에서 채움).

## 3. 통계 (McNemar + 부트스트랩)

```bash
python -m src.cli stats \
  reports/scoring/score_ontology.json reports/scoring/score_guard.json \
  --out reports/stats_det.json
```

실측 출력:

```
McNemar (ontology vs guard): b=0 c=0 p=1.0000 [no_discordant]
Bootstrap F1 (guard): 0.632 95% CI [0.424, 0.791] (n_boot=2000)
```

- McNemar 는 두 조건의 케이스별 정/오답을 `case_id` 로 짝지어 비교한다. discordant<25 면 정확 이항검정.
- 의미 있는 McNemar p-value 는 **baseline vs guard** 짝에서 나온다 → baseline 라이브 채점(§3 후속) 후 다시 실행.

## 4. 라이브 풀런 (Ollama 필요)

실제 LLM 추출부터 검증까지 한 모드를 끝까지 실행한다.

### 4.1 Ollama 준비

```bash
ollama serve                 # 백그라운드. 이미 떠 있으면 생략
ollama list                  # gemma4:31b (19.9GB) 존재 확인
```

서버는 `http://localhost:11434`. `OllamaClient.ping()` 으로 확인된다.

### 4.2 실행

```bash
python scripts/harness_run.py --mode guard --seed 42
```

실측 출력:

```
Ollama version: 0.24.0
[DONE] mode=guard wall=174s tokens=24168
  guard_events=29 rejects=0
  shacl_conforms=True
  cross_check by_status={'needs_review': 8, 'missing_evidence': 6}
  -> database/gemma4_harness/run_live_guard_seed42
```

- 소요 ~174s (2-pass vision 추출이 대부분). 모델 로드 포함 첫 실행은 더 길 수 있다.
- `--mode` 는 `baseline | ontology | guard`. baseline 은 추출만, ontology 는 +ABox/SHACL/cross_check, guard 는 +G1/G2/G3.

### 4.3 산출물

`database/gemma4_harness/run_live_<mode>_seed<N>/` 에 생성:

| 파일 | 내용 |
|---|---|
| `harness_result.json` | HarnessResult 전체 (추출 14필드 + guard_log + cross_check) |
| `abox.ttl` | RDF ABox (Turtle) |
| `shacl_report.txt` | SHACL 검증 리포트 |
| `manifest.json` | 실행 메타 (seed, model, sha256, 토큰, 시간 — INTERFACES §5) |

> **실증된 관찰:** 라이브 결과의 `fund.inception_date` 가 "2025년 7월 22일"(계약서) vs "2025년7월22일"(IM) — 공백만 다른데 `needs_review` 로 분류된다. §1 의 결정적 채점이 예측한 "정규화 없으면 정밀도 손실"이 실데이터에서 그대로 재현된다.

## 5. CLI = `dnb run` (대안)

`scripts/harness_run.py` 대신 기존 풀 파이프라인을 호출:

```bash
python -m src.cli run --seeds 42 --with-normalize --with-judge
```

→ `scripts/extract_full_pipeline.py` 를 실행 (Gemma 추출 + 가드 + 온톨로지 + cross_check, 옵션으로 Claude 정규화/judge). 산출은 `database/gemma4_full/run_NN_seedM/`.

## 6. 3조건 비교 (non-harness / harness / harness+norm)

같은 골든 30케이스·같은 입력으로 세 조건을 비교한다. 차이는 *방법*뿐.

| 조건 | 구성 | 실행 |
|---|---|---|
| ① non-harness | LLM(gemma4:31b) 단독 판정. 온톨로지·가드 없음 | `scripts/baseline_judge.py` |
| ② harness | 가드(G1/G2/G3) + cross_check, 결정적 | `dnb score --mode guard` |
| ③ harness+norm | ② + normalization + judge (Claude) | `scripts/score_harness_norm.py` |

### 6.1 세 조건 산출

```bash
# ① non-harness (Ollama 필요)
python scripts/baseline_judge.py --seed 42
# ② harness (결정적, LLM 불필요)
python -m src.cli score --mode guard --out reports/scoring/score_guard.json
# ③ harness+norm (Claude 필요 — .env 의 ANTHROPIC_API_KEY)
python scripts/score_harness_norm.py
```

실측 (gemma4:31b 추출/판정, claude-sonnet-4-6 정규화/judge):

```
① non-harness   P=0.889 R=0.667 F1=0.762 acc=0.808  TP8  FP1  FN4 TN13   (168s)
② harness       P=0.462 R=1.000 F1=0.632 acc=0.462  TP12 FP14 FN0 TN0    (<1s)
③ harness+norm  P=0.733 R=0.917 F1=0.815 acc=0.808  TP11 FP4  FN1 TN10   (123s)
```

### 6.2 통계

```bash
python -m src.cli stats reports/scoring/score_baseline.json reports/scoring/score_guard.json --out reports/stats_off_vs_on.json
python -m src.cli stats reports/scoring/score_baseline.json reports/scoring/score_harness_norm.json --out reports/stats_base_vs_full.json
```

실측: `①vs② McNemar b=13 c=4 p=0.0490`(유의) · `①vs③ b=3 c=3 p=1.0000`(정확도 동률) · `Bootstrap F1(③) 95% CI [0.621, 0.952]`.

### 6.3 결과표 (잠정 골든 기준)

| 지표 | ① non-harness | ② harness | ③ harness+norm |
|---|:---:|:---:|:---:|
| F1 | 0.762 | 0.632 | **0.815** |
| Recall ★ | 0.667 | **1.000** | 0.917 |
| Precision | **0.889** | 0.462 | 0.733 |
| Accuracy | 0.808 | 0.462 | 0.808 |
| 환각률 | 0.000 | 0.000 | 0.000 |
| 혼동(TP/FP/FN/TN) | 8/1/4/13 | 12/14/0/0 | 11/4/1/10 |

### 6.4 핵심 발견

- **③ 완성형이 F1 최고(0.815) — ① LLM 단독(0.762)을 이긴다.** ②→③ 에서 정규화/judge 가 정상 표기차이 오탐을 14→4 로 줄여 정밀도 0.46→0.73 회복.
- **① 이 놓친 치명 4건**(C021 단위함정·C022 날짜추론·C029 가짜인용·C030 보수한도초과)을 ② 가드는 전부 차단 (McNemar p=0.049, 유의).
- **⚠️ ③ 의 재현율 역행 (1.0→0.917)**: `C021`(판매보수 0.3% vs 0.03%, 10배 자릿수 함정)을 Claude judge 가 "동일"로 정규화해 **놓침**(② 는 잡았음). 같은 변조 C020(0.5 vs 0.05)은 잡아 judge 의 숫자 비교가 불안정.
  → **교훈**: 보수(천분율/소수점) 단위 비교는 judge 위임 대신 **G3 에서 결정적으로** 처리해야 함 (재현율 우선).
- **③ 의 남은 오탐 4건**: C002 약칭·C006 만기(절대 vs 기간)·C007 OCR 오타·C018 부재 동치 — 모두 `llm_judge` 신호의 어려운 의미동등 케이스.
- **주의**: 골든셋 freeze 전 잠정치. 경향(③ 이 F1 최고, ② 가 재현율 보장, judge 의 단위 누락 위험)은 견고하다.

## 7. Ontology Policy 비교

`ontology_policy`는 G1/G2/G3 이후 `ontology/field_policies.yaml` 기반 canonical comparison을 먼저 수행한다. 결정론으로 확정된 필드는 LLM을 호출하지 않는다.

```bash
# 결정론 policy 비교 (LLM 불필요)
python -m src.cli score --mode ontology_policy --out reports/scoring/score_ontology_policy.json

# Claude judge fallback 포함 (ANTHROPIC_API_KEY 필요)
python scripts/score_ontology_policy.py
```

`ontology_policy_judge`는 canonical이 확정하지 못하고 field policy가 허용한 필드에만 Claude judge fallback을 적용한다. Claude normalization은 사용하지 않는다. 이 경로는 C021 같은 보수 단위 자릿수 함정을 LLM judge에 맡기기 전에 결정론 canonical comparison으로 먼저 확정하기 위한 추가 비교 조건이다.

실측(`needs_review`를 `review`로 분리한 현재 채점 기준):

| 조건 | Precision | Recall | F1 | 모르겠다 |
|---|---:|---:|---:|---:|
| ontology_policy | 1.000 | 0.583 | 0.737 | 13/30 |
| ontology_policy_judge | 0.800 | 1.000 | 0.889 | 0/30 |

`redemption_terms.is_redeemable`은 generic same/different judge 대신 전용 LLM classifier를 사용한다. LLM이 계약서/IM 각각을 `yes|no|conditional|unknown`으로 독립 분류하고, 코드가 `yes/no` 조합만 최종 match/mismatch로 확정한다. `conditional`, `unknown`, 또는 낮은 confidence는 review로 남긴다.

## 재현성 규칙

- 같은 입력 PDF(`database/raw_data/`)와 같은 골든셋(`tests/golden/golden_master.csv`)을 쓴다.
- seed · model id · 토큰 · timestamp 는 `manifest.json` 에 남는다.
- 자동 생성 산출물(`reports/scoring/`, `database/gemma4_harness/`)은 기본적으로 커밋하지 않는다.
- 채점 매핑(`FINAL_TO_PREDICTED`)이 바뀌면 모든 점수가 바뀐다 — `docs/GOLDENSET.md §7` 을 단일 진실 소스로 본다.
