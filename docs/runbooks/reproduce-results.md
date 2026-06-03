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

실측 출력:

```
[ontology] P=0.462 R=1.000 F1=0.632 환각=0.000  ->  reports/scoring/score_ontology.json
[guard]    P=0.462 R=1.000 F1=0.632 환각=0.000  ->  reports/scoring/score_guard.json
```

- `--contract-pages` / `--im-pages` 는 G2 출처 범위 기준(기본 22 / 32, 실제 PDF 페이지 수).
- `by_signal` 에서 `g2_citation` · `g3_constraint+shacl` 의 `hit_rate=1.0` → C029(가짜 인용)·C030(SHACL 위반)을 가드가 정확히 잡는다.

> **해석:** ontology/guard 가 동일 지표인 이유 — 결정적 cross_check 는 raw_text 가 다르면 전부 `needs_review`(=mismatch)로 본다. 그래서 변조는 전부 잡지만(R=1.0), 정규화가 필요한 정상 케이스(천분율·약칭·의미동등)를 mismatch 로 오탐해 정밀도가 0.46 에 머문다. 정밀도 개선은 normalization/judge(Claude) 단계의 몫이다 (§3 참조).

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

## 6. OFF vs ON 비교 (3조건 실증)

"온톨로지·하네스를 **안 썼을 때(baseline)** vs **썼을 때(guard)**"를 같은 골든 30케이스·같은 입력으로 비교한다. 차이는 *방법*뿐 — baseline 은 LLM 단독 판정, guard 는 온톨로지+하네스 결정적 로직.

### 6.1 baseline 라이브 채점 (LLM 단독, Ollama 필요)

```bash
python scripts/baseline_judge.py --seed 42
```

실측 출력 (gemma4:31b, 30케이스 168s):

```
[baseline DONE] 30케이스 wall=168s
  P=0.889 R=0.667 F1=0.762 acc=0.808 환각=0.000
  TP=8 FP=1 FN=4 TN=13 missing제외=4
```

### 6.2 통계 비교

```bash
python -m src.cli stats \
  reports/scoring/score_baseline.json reports/scoring/score_guard.json \
  --out reports/stats_off_vs_on.json
```

실측: `McNemar (baseline vs guard): b=13 c=4 p=0.0490 [exact_binomial]` → **유의수준 0.05 에서 유의미한 차이.**

### 6.3 결과표 (잠정 골든 기준)

| 지표 | OFF · baseline (LLM 단독) | ON · guard (온톨로지+하네스) |
|---|:---:|:---:|
| Recall ★ | 0.667 | **1.000** |
| Precision | **0.889** | 0.462 |
| F1 | 0.762 | 0.632 |
| Accuracy | 0.808 | 0.462 |
| 환각률 | 0.000 | 0.000 |
| 혼동행렬 | TP8 FP1 **FN4** TN13 | **TP12** FP14 FN0 TN0 |

### 6.4 핵심 — baseline 이 놓친 4건을 하네스가 전부 잡음

| 케이스 | 변조 유형 | LLM 단독 | 하네스 | 놓친 이유 |
|---|---|:---:|:---:|---|
| C021 | decimal_shift | ❌ match | ✅ mismatch | 숫자만 보고 0.3=0.3 합격 (단위 함정) |
| C022 | date_shift | ❌ match | ✅ mismatch | '3년'을 절대일자와 대조 안 함 |
| C029 | fake_citation | ❌ match | ✅ mismatch | 값 같으니 합격 — 페이지 위조는 G2 전용 |
| C030 | shacl_violation | ❌ match | ✅ mismatch | 8.9=8.9 숫자 같아 합격 — 보수 한도는 G3/SHACL 전용 |

### 6.5 해석

- **가설 증명**: LLM 단독은 가장 위험한 4건(단위함정·날짜추론·가짜인용·보수한도초과)을 "일치"로 통과 → 컴플라이언스 사고. 하네스는 재현율 1.0 으로 전부 차단 (McNemar p=0.049).
- **하네스의 현재 약점은 정밀도**: 결정적 단계만으론 정상 표기차이를 오탐(FP14). baseline 의 정밀도 0.889 가 목표선 → **normalization + LLM judge(Claude)를 켜면 재현율 1.0 을 유지하며 정밀도 회복**이 완성형(②/③ 가 ① 을 이기는 그림).
- **주의**: 골든셋 freeze 전 잠정치. 경향(LLM 단독은 치명 4건 누락, 하네스는 전부 탐지)과 McNemar 유의성은 견고하다.

## 재현성 규칙

- 같은 입력 PDF(`database/raw_data/`)와 같은 골든셋(`tests/golden/golden_master.csv`)을 쓴다.
- seed · model id · 토큰 · timestamp 는 `manifest.json` 에 남는다.
- 자동 생성 산출물(`reports/scoring/`, `database/gemma4_harness/`)은 기본적으로 커밋하지 않는다.
- 채점 매핑(`GOLD_TO_FINAL`)이 바뀌면 모든 점수가 바뀐다 — `docs/GOLDENSET.md §7` 을 단일 진실 소스로 본다.
