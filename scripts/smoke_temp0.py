"""temp=0 smoke — Q4 양자화에서 token 폭주(degenerate) 발생 여부 확인.

같은 prompt + seed 로 temp=0.0 / 0.05 / 0.1 비교.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.client.ollama_client import OllamaClient  # noqa: E402

PROMPT = (
    "다음 텍스트에서 펀드명과 운용보수를 추출해 JSON으로만 답하세요.\n\n"
    "이 집합투자기구의 명칭은 '이지스블랙 ON 일반사모투자신탁제 1 호'라 한다.\n"
    "집합투자업자보수율 : 연 1,000분의 8.9\n"
    "신탁업자보수율 : 연 1,000분의 0.5\n"
)
SCHEMA = {
    "type": "object",
    "properties": {
        "fund_name": {"type": "string"},
        "management_fee": {"type": "string"},
        "trust_fee": {"type": "string"},
    },
    "required": ["fund_name", "management_fee", "trust_fee"],
}


def run_one(client: OllamaClient, label: str) -> None:
    r = client.generate(prompt=PROMPT, json_schema=SCHEMA)
    print(f"\n[{label}] temp={client.temperature} seed={client.seed} eval_ms={r.eval_ms}")
    try:
        parsed = json.loads(r.response_text)
        print(f"  parsed: {parsed}")
    except json.JSONDecodeError as e:
        print(f"  RAW: {r.response_text[:200]!r}")
        print(f"  PARSE ERROR: {e}")


def main() -> int:
    for temp in (0.0, 0.05, 0.1):
        client = OllamaClient(model="gemma4:31b", seed=42, temperature=temp, num_predict=512)
        # 같은 temp 로 두 번 호출 → 결정론 확인
        run_one(client, f"temp{temp}_first")
        run_one(client, f"temp{temp}_second")
    return 0


if __name__ == "__main__":
    sys.exit(main())
