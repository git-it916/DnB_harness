# 온보딩 가이드 — 시작하는 사람을 위해

> 이 폴더는 "리포지토리에 아무것도 없을 때 우리는 어디서부터 어떻게 시작하는가"를 멤버별로 정리한 가이드입니다.
> 각자 자기 트랙 파일을 펴고, 1주차 체크리스트부터 따라가세요. 헷갈리는 용어는 끝의 [용어사전](#용어사전)에 정리되어 있습니다.

---

## 0. 멤버별 가이드 — 자기 파일을 펴세요

| 파일 | 담당 | 핵심 미션 |
|------|------|----------|
| [01_lead_harness.md](./01_lead_harness.md) | 신승훈 | PM·하네스 코어·골든셋 라벨링 시작 |
| [02_agent_prompt.md](./02_agent_prompt.md) | 노종현 | 프롬프트·구조화 출력·LLM 호출 흐름 |
| [03_guards.md](./03_guards.md) | 조건 | 가드 5종 설계·ablation 실험 |
| [04_pipeline.md](./04_pipeline.md) | 한승연 | CLI·리포트 자동화·전체 파이프라인 |
| [05_docs.md](./05_docs.md) | 김리나 | 관련 연구·문서·라벨링 페어·발표 |

각 가이드는 **0주차(환경 셋업) → 1주차(첫 산출물) → 2주차(본격 시작)** 의 3단 구조입니다.

---

## 1. 모두가 해야 할 0주차 공통 셋업

### (1) 저장소 받기

```bash
# Windows PowerShell
cd "C:\Users\<your-user>\<your-folder>"
git clone https://github.com/<우리-organization>/DnB_harness.git
cd DnB_harness
```

### (2) Conda 가상환경 활성화

승훈이 이미 `dnb_harness` 환경을 만들어 뒀습니다 (Python 3.11 + requirements.txt 설치 완료).

```bash
conda activate dnb_harness
# 동작 확인
python -c "import anthropic; print(anthropic.__version__)"
```

만약 `dnb_harness` 환경이 없다고 나오면:
```bash
conda env list   # 환경 목록 확인
# 없으면 (자기 PC에 처음 받았을 때):
conda create -n dnb_harness python=3.11 -y
conda activate dnb_harness
pip install -r requirements.txt
```

### (3) API 키 설정

루트에 `.env` 파일을 만듭니다 (절대 git에 커밋 금지 — `.gitignore`에 들어가 있어야 함).

```env
# .env
ANTHROPIC_API_KEY=sk-ant-api03-...자기-키...
```

키 발급: <https://console.anthropic.com/> → Settings → API Keys.
**팀 공용 키는 슬랙에서 받아오세요.** 자기 계정으로도 OK ($5 무료 크레딧).

### (4) 첫 호출 확인 ("Hello Claude")

`scripts/hello_claude.py` 라는 파일을 만들고 다음을 넣고 실행:

```python
import os
from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic()  # API_KEY는 env에서 자동으로 읽음

resp = client.messages.create(
    model="claude-haiku-4-5-20251001",  # 테스트는 싼 Haiku로
    max_tokens=100,
    messages=[{"role": "user", "content": "한 줄로 자기소개해."}],
)
print(resp.content[0].text)
print(f"입력 토큰: {resp.usage.input_tokens}, 출력 토큰: {resp.usage.output_tokens}")
```

```bash
python scripts/hello_claude.py
```

답이 한 줄 나오면 성공. 이게 안 되면 0주차 끝낼 수 없으니 슬랙에 도움 요청.

### (5) 필독 문서

순서대로 30분 잡고 읽기:
1. [`PLAN.md`](../PLAN.md) — 우리가 뭘 만들고 뭘 검증하려는지
2. [`R&R.md`](../R&R.md) — 누가 뭘 책임지는지 + RACI 표
3. **자기 트랙 온보딩 파일** (위 표)

---

## 2. 모두가 따르는 운영 룰 (5줄 요약)

1. **PR로 작업** — 직접 `main`에 push 금지. 브랜치 만들고 PR → 리뷰 1명 → 머지.
2. **24시간 막히면 슬랙** — 혼자 끌어안지 말 것.
3. **PDF 외부 업로드 금지** — 펀드 자료는 Claude API 외 어떤 외부 서비스에도 올리면 안 됨.
4. **결과는 reports/<run_id>/에 저장** — 사후 재현/재채점을 위해 raw 응답까지 모두 저장.
5. **PLAN.md = 진실의 원천** — 가설 검증/기각, 스코프 변경은 PLAN에 반영.

---

## 3. 자주 막히는 곳

| 증상 | 해결 |
|------|------|
| `conda: command not found` | Miniconda 또는 Anaconda 설치 필요. PowerShell에서 `where.exe conda` 로 경로 확인. |
| `ANTHROPIC_API_KEY not found` | `.env` 파일이 루트에 있는지 + `python-dotenv` 설치됐는지 확인. `load_dotenv()` 빠진 거 아닌지. |
| `ModuleNotFoundError: anthropic` | `conda activate dnb_harness` 안 한 채 다른 환경에서 실행 중. |
| 한글 파일명/경로 깨짐 | Windows에서 `chcp 65001` 한 번 실행 (UTF-8 모드). |
| Claude API 401/403 | 키 오타 또는 만료. console에서 새 키 발급. |
| Claude API 429 (rate limit) | `tenacity` 재시도 데코레이터 + 호출 간 sleep. |

---

## <a name="용어사전"></a>4. 용어 사전 (5분 컷)

| 용어 | 우리 프로젝트 맥락에서의 의미 |
|------|----------------------------|
| **하네스 (Harness)** | LLM 자체가 아니라, LLM을 감싸서 입력 검사·출력 검증·평가까지 자동으로 해주는 **장치 전체**. 우리 프로젝트의 본체. |
| **골든셋 (Golden Set, GT, Ground Truth)** | "정답지". 사람이 미리 라벨링해둔 (질문, 정답) 쌍. LLM이 맞혔는지 자동 채점할 때 쓰임. |
| **앵커 사실 (Anchor Facts)** | 한 펀드 문서에서 뽑은 핵심 사실 25~35개 (펀드명, 수수료, 만기 등). 우리 골든셋의 한 종류. |
| **Perturbation (변조)** | 원본 PDF에 의도적으로 미세 수정(예: 0.7%→0.75%)을 주입해 만든 가짜 모순. LLM이 이 모순을 잡아내는지 테스트. |
| **Eval / Scorer** | LLM 출력과 골든셋을 비교해 점수(F1, EM 등)를 계산하는 코드. **LLM 호출 없는 순수 함수**로 만든다. |
| **Precision / Recall / F1** | 분류 평가 기본 3종. Precision = "잡은 것 중 진짜 맞는 비율", Recall = "진짜 중 잡은 비율", F1 = 둘의 조화평균. |
| **F1 = 0.91이란?** | 100점 만점에 91점쯤. 0.95 넘으면 실무 후보, 0.85 미만이면 운영 부적합. |
| **Cohen's κ (kappa)** | 두 사람(또는 사람 vs LLM)이 같은 라벨을 얼마나 일치시키는지. 0.7+ 면 신뢰할 만한 라벨. |
| **Prompt Caching** | 매 호출마다 똑같은 PDF를 다시 보내면 비쌈. 캐시에 올려두고 변하는 부분만 보내면 90% 절감. 단, **5분 TTL**. |
| **Tool Use / Structured Output** | LLM에게 "이런 JSON 구조로 답해줘"를 강제하는 Anthropic 기능. 우리는 자유 텍스트 대신 항상 구조화 JSON으로 받는다. |
| **RAG (Retrieval-Augmented Generation)** | "관련 조항만 골라 LLM에 주기". 100쪽 문서 다 안 주고 관련 5쪽만 줘서 비용·정확도 동시에 잡는 기법. |
| **Ablation** | "한 부분을 빼면 결과가 얼마나 나빠지나?" 실험. 가드 ON/OFF로 누락률 변화 보는 게 우리 핵심 실험. |
| **DoD (Definition of Done)** | "이 작업이 끝났다고 말할 수 있는 기준". 각 마일스톤에 명시되어 있음. |
