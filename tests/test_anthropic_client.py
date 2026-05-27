import json

import pytest

from src.client.anthropic_client import _parse_json_response


def test_parse_json_response_accepts_markdown_json_fence():
    payload = {"field": "fee_schedule.management_fee", "status": "same"}

    assert _parse_json_response(f"```json\n{json.dumps(payload)}\n```") == payload


def test_parse_json_response_reports_invalid_json_after_fence_is_removed():
    with pytest.raises(ValueError, match="LLM response was not valid JSON"):
        _parse_json_response('```json\n{"raw_text": "명칭은 "펀드"라 한다"}\n```')
