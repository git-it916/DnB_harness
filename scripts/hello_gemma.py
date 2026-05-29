"""Gemma 4 smoke test — Ollama JSON Schema 강제 추출이 한국어 + 결정론적으로 동작하는지 확인.

실행:
    conda run -n dnb_harness python scripts/hello_gemma.py

요구:
    - Ollama 0.20+ 실행 중 (localhost:11434)
    - gemma4:31b 모델 풀 완료
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import requests


OLLAMA_URL = "http://localhost:11434"
MODEL = "gemma4:31b"
SEED = 42


def generate_json(prompt: str, schema: dict[str, Any], *, temperature: float = 0.1) -> tuple[dict[str, Any], int]:
    """Ollama generate API 호출 + JSON Schema 강제 + 평가 시간(ms) 반환."""
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": MODEL,
            "prompt": prompt,
            "format": schema,
            "stream": False,
            "options": {
                "temperature": temperature,
                "seed": SEED,
                "num_predict": 1024,
            },
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    eval_ms = data.get("eval_duration", 0) // 1_000_000
    return json.loads(data["response"]), eval_ms


def main() -> int:
    print("=" * 60)
    print(f"Gemma 4 Smoke Test — model={MODEL}, seed={SEED}")
    print("=" * 60)

    # 1) 서버 ping
    try:
        version = requests.get(f"{OLLAMA_URL}/api/version", timeout=5).json()
        print(f"[OK] Ollama version: {version['version']}")
    except Exception as e:
        print(f"[FAIL] Ollama server unreachable: {e}")
        return 1

    # 2) 단일 필드 추출 (펀드명)
    print("\n[TEST 1] 펀드명 단일 필드 추출")
    schema_simple = {
        "type": "object",
        "properties": {"fund_name": {"type": "string"}},
        "required": ["fund_name"],
    }
    prompt = (
        "다음 텍스트에서 펀드명을 추출해 JSON으로만 답하세요.\n\n"
        "이 집합투자기구의 명칭은 '이지스블랙 ON 일반사모투자신탁제 1 호'라 한다."
    )
    try:
        result, ms = generate_json(prompt, schema_simple)
        print(f"  result: {result}")
        print(f"  eval_ms: {ms}")
        assert "fund_name" in result, "fund_name key missing"
        assert "이지스" in result["fund_name"] or "ON" in result["fund_name"], (
            f"Korean extraction failed: {result['fund_name']!r}"
        )
        print("  [PASS]")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1

    # 3) 결정론 (동일 시드 두 번 호출 결과 비교)
    print("\n[TEST 2] 결정론 (seed=42, temp=0.1 두 번)")
    r1, _ = generate_json(prompt, schema_simple)
    r2, _ = generate_json(prompt, schema_simple)
    if r1 == r2:
        print(f"  [PASS] identical: {r1}")
    else:
        print(f"  [WARN] non-deterministic: {r1} vs {r2}")

    # 4) 14 필드 mini schema (운용보수만)
    print("\n[TEST 3] 중첩 스키마 — 운용보수 (contract 측)")
    schema_fee = {
        "type": "object",
        "properties": {
            "management_fee": {
                "type": "object",
                "properties": {
                    "raw_text": {"type": "string"},
                    "page": {"type": "integer"},
                    "value": {"type": ["string", "null"]},
                    "unit": {"type": ["string", "null"]},
                },
                "required": ["raw_text", "page"],
            }
        },
        "required": ["management_fee"],
    }
    prompt_fee = (
        "다음 신탁계약서 발췌에서 운용보수를 추출하세요.\n"
        "raw_text는 원문 그대로, page는 정수.\n\n"
        "[Page 15]\n집합투자업자보수율 : 연 1,000분의 8.9\n"
        "신탁업자보수율 : 연 1,000분의 0.5\n"
    )
    try:
        result, ms = generate_json(prompt_fee, schema_fee)
        print(f"  result: {json.dumps(result, ensure_ascii=False, indent=2)}")
        print(f"  eval_ms: {ms}")
        fee = result["management_fee"]
        assert "8.9" in fee["raw_text"], f"raw_text wrong: {fee['raw_text']!r}"
        assert fee["page"] == 15, f"page wrong: {fee['page']}"
        print("  [PASS]")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1

    # 5) 빈 필드 (null) 처리
    print("\n[TEST 4] 본문에 없는 값 — null 반환")
    schema_optional = {
        "type": "object",
        "properties": {
            "trust_fee": {"type": ["string", "null"]},
        },
        "required": ["trust_fee"],
    }
    prompt_missing = (
        "다음 텍스트에서 신탁보수(trust_fee)를 추출하세요. 없으면 null.\n\n"
        "[Page 1]\n이지스블랙 ON 일반사모투자신탁제 1 호\n폐쇄형 사모펀드입니다.\n"
    )
    try:
        result, ms = generate_json(prompt_missing, schema_optional)
        print(f"  result: {result}, eval_ms={ms}")
        if result["trust_fee"] is None:
            print("  [PASS] 본문에 없으면 null 반환")
        else:
            print(f"  [WARN] 본문 없는데 환각 추출됨: {result['trust_fee']!r}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1

    print("\n" + "=" * 60)
    print("Smoke test 통과. Gemma 4 + JSON Schema 모드 사용 가능.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
