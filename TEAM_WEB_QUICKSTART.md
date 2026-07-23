# DnB Harness 로컬 검토 웹 실행 가이드



## 1. 필요한 프로그램

다음 프로그램이 설치되어 있어야 합니다.

- Git
- Python 3.11 이상
- `uv`
- Node.js LTS
- `pnpm`

터미널 또는 PowerShell에서 설치 여부를 확인하세요.

```bash
git --version
uv --version
node --version
pnpm --version
```

명령어를 찾을 수 없다는 메시지가 나오면 해당 프로그램을 먼저 설치해야 합니다.

- Git: [https://git-scm.com/downloads](https://git-scm.com/downloads)
- uv: [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js LTS: [https://nodejs.org/](https://nodejs.org/)
- pnpm: Node.js 설치 후 `npm install -g pnpm`

macOS에서 Homebrew를 사용한다면 다음 명령으로 설치할 수 있습니다.

```bash
brew install git uv node pnpm
```

## 2. 저장소 받기

처음 설치하는 경우 원하는 작업 폴더에서 다음 명령을 실행합니다.

```bash
git clone https://github.com/git-it916/DnB_harness.git
cd DnB_harness
```

이미 저장소를 받은 경우에는 저장소 폴더로 이동한 뒤 최신 코드를 받습니다.

```bash
cd DnB_harness
git pull
```

> `git pull` 전에 본인이 수정 중인 파일이 있다면 변경 내용을 먼저 확인하세요. 다른 팀원의 작업을 임의로 삭제하거나 덮어쓰지 마세요.

## 3. Anthropic API 키 준비

PDF 분석을 실제로 실행하려면 Anthropic API 키가 필요합니다.

다음 중 팀에서 합의한 방법을 사용하세요.

1. 각 팀원이 자신의 Anthropic API 키를 발급받아 사용
2. 프로젝트용 API 키를 별도로 발급하고 비용 및 사용량 담당자를 지정하여 사용

개인 키를 메신저, 문서 또는 Git에 올리지 마세요. 일반 Claude 웹 구독과 Anthropic API 사용 권한 및 크레딧은 별도로 관리될 수 있으므로 Anthropic Console에서 API 사용 가능 여부와 결제 설정을 확인하세요.

저장소 최상위 폴더, 즉 `pyproject.toml`과 같은 위치에 `.env` 파일을 만들고 아래와 같이 입력합니다.

```text
ANTHROPIC_API_KEY=여기에_본인의_API_키를_입력
```

기본 모델은 `claude-sonnet-4-6`입니다. 팀에서 다른 모델을 사용하기로 합의한 경우에만 다음처럼 지정합니다.

```text
ANTHROPIC_API_KEY=여기에_본인의_API_키를_입력
ANTHROPIC_MODEL=팀에서_합의한_모델명
```

주의:

- 따옴표는 필요하지 않습니다.
- `ANTHROPIC_API_KEY=` 뒤에 공백을 넣지 마세요.
- 실제 API 키를 터미널 출력, 스크린샷 또는 오류 문의 글에 포함하지 마세요.
- `.env`는 이 저장소의 `.gitignore`에 등록되어 있지만, 커밋 전에 항상 `git status`로 다시 확인하세요.

## 4. 최초 설치 및 웹 빌드

저장소 최상위 폴더에서 실행합니다.

```bash
uv sync --dev
cd web
pnpm install
pnpm build
cd ..
```

각 명령이 오류 없이 끝나야 합니다. `pnpm build`가 완료되면 FastAPI 서버가 빌드된 웹 화면을 함께 제공합니다.

## 5. 웹 실행

저장소 최상위 폴더에서 다음 명령을 실행합니다.

```bash
uv run python -m src.web_api
```

터미널을 닫지 않은 상태에서 브라우저로 다음 주소를 엽니다.

[http://127.0.0.1:8000](http://127.0.0.1:8000)

서버 동작 여부만 확인하려면 다른 터미널에서 다음 주소를 열거나 명령을 실행합니다.

```bash
curl http://127.0.0.1:8000/api/v1/health
```

정상 응답:

```json
{"status":"ok","local_only":true}
```

웹 서버를 종료하려면 실행 중인 터미널에서 `Ctrl+C`를 누릅니다.

## 6. 웹 사용 방법

1. 신탁계약서 PDF를 `계약서` 입력란에 선택합니다.
2. 투자제안서 PDF를 `IM` 입력란에 선택합니다.
3. 검토 실행 버튼을 누릅니다.
4. 추출과 판정이 끝날 때까지 상태 표시를 확인합니다.
5. 각 필드의 계약서 값, IM 값, 원문 근거, 가드 및 canonical 판정 경로를 확인합니다.
6. `사용자 확인 필요` 항목은 다음 중 하나로 판단합니다.
  - `같음`: 동일한 의미로 확정
  - `다름`: 불일치로 확정
  - `판단 보류`: 결정을 보류
7. 펀드명·운용사·신탁업자·판매사에서 `같음`을 선택한 경우에만, 필요하면 앞으로도 같은 명칭으로 사용할 Alias를 로컬에 저장합니다.

업로드 파일은 파일당 최대 50MB이며 PDF만 지원합니다.

## 7. 다음 실행부터 사용하는 명령

프론트엔드 코드 변경이 없다면 저장소 최상위 폴더에서 다음 명령만 실행하면 됩니다.

```bash
uv run python -m src.web_api
```

최신 코드를 받은 뒤에는 의존성 또는 웹 코드가 변경되었을 수 있으므로 다음 순서를 권장합니다.

```bash
git pull
uv sync --dev
cd web
pnpm install
pnpm build
cd ..
uv run python -m src.web_api
```

## 8. 8000 포트가 이미 사용 중인 경우

macOS/Linux:

```bash
DNB_PORT=8010 uv run python -m src.web_api
```

Windows PowerShell:

```powershell
$env:DNB_PORT="8010"
uv run python -m src.web_api
```

그다음 브라우저에서 다음 주소를 엽니다.

[http://127.0.0.1:8010](http://127.0.0.1:8010)

## 9. 자주 발생하는 문제

### `uv: command not found` 또는 `uv`를 찾을 수 없음

`uv`를 설치한 뒤 터미널을 완전히 닫고 다시 여세요.

- 설치 안내: [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)

### `pnpm: command not found` 또는 `pnpm`을 찾을 수 없음

Node.js가 설치되어 있는지 확인한 뒤 실행합니다.

```bash
npm install -g pnpm
pnpm --version
```

### 브라우저에 화면이 나오지 않음

1. 서버를 실행한 터미널이 계속 열려 있는지 확인합니다.
2. 주소가 `http://127.0.0.1:8000`인지 확인합니다.
3. health endpoint를 확인합니다.

```bash
curl http://127.0.0.1:8000/api/v1/health
```

4. 8000 포트 충돌이 의심되면 8절의 방법으로 8010 포트를 사용합니다.

### 화면은 열리지만 PDF 검토가 실패함

다음을 순서대로 확인합니다.

1. 저장소 최상위 폴더에 `.env`가 있는지 확인합니다.
2. `.env`에 `ANTHROPIC_API_KEY`가 정확히 입력되어 있는지 확인합니다.
3. Anthropic Console에서 API 키가 활성 상태인지 확인합니다.
4. API 크레딧 또는 결제 한도가 남아 있는지 확인합니다.
5. 업로드한 두 파일이 정상적인 PDF이고 각각 50MB 이하인지 확인합니다.
6. 서버를 실행한 터미널의 오류 메시지를 확인하되, 공유 전에 API 키와 계약 관련 민감정보를 제거합니다.

### 웹 화면이 예전 버전으로 보임

최신 코드를 받은 뒤 웹을 다시 빌드하고 서버를 재시작합니다.

```bash
git pull
uv sync --dev
cd web
pnpm install
pnpm build
cd ..
uv run python -m src.web_api
```

## 10. 로컬 데이터 위치와 초기화

기본 실행 데이터는 저장소의 `var/` 아래에 저장됩니다.

```text
var/
  dnb.sqlite3
  runs/<run_id>/
    input/contract.pdf
    input/im.pdf
    review_result.json
    abox.ttl
    shacl_report.txt
```

이 폴더에는 원본 PDF와 검토 결과가 포함될 수 있으므로 외부에 공유하거나 Git에 올리지 마세요.

기존 실행 기록을 삭제하면 복구할 수 없습니다. `var/` 삭제가 필요하다면 먼저 필요한 결과가 없는지 확인하고, 팀 데이터 관리 규칙에 따라 직접 삭제하세요.

## 11. 문의할 때 함께 전달할 정보

문제가 해결되지 않으면 다음 정보만 정리해서 팀에 전달하세요.

- 사용 중인 운영체제
- 실패한 단계와 실행한 명령
- 서버 터미널에 나온 오류 메시지
- `git status --short --branch` 결과
- `uv --version`, `node --version`, `pnpm --version` 결과

API 키, `.env` 내용, 실제 계약서/IM 원문, `var/`의 PDF는 공유하지 마세요.