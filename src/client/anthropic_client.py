import json
import os
from typing import Any

from dotenv import load_dotenv

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


class AnthropicJSONClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        max_tokens: int = 1024,
        temperature: float = 0,
    ) -> None:
        load_dotenv()
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        self.model = os.getenv("ANTHROPIC_MODEL", model)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = None
        self.last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return self.complete_json_with_content(
            system_prompt=system_prompt,
            content=[{"type": "text", "text": user_prompt}],
        )

    def complete_json_with_content(
        self,
        *,
        system_prompt: str,
        content: list[dict[str, Any]],
    ) -> dict[str, Any]:
        client = self._anthropic_client()
        message = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        self._record_usage(message)
        return _parse_json_response(_message_text(message))

    def complete_text_with_content(
        self,
        *,
        system_prompt: str,
        content: list[dict[str, Any]],
    ) -> str:
        client = self._anthropic_client()
        message = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        self._record_usage(message)
        return _message_text(message)

    def _record_usage(self, message) -> None:
        usage = getattr(message, "usage", None)
        if usage is None:
            return
        for key in self.last_usage:
            self.last_usage[key] += int(getattr(usage, key, 0) or 0)

    def _anthropic_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise RuntimeError(
                    "anthropic package is not installed. Install project dependencies first."
                ) from exc
            self._client = Anthropic(api_key=self.api_key)
        return self._client


def _message_text(message) -> str:
    chunks = []
    for block in message.content:
        text = getattr(block, "text", None)
        if text is not None:
            chunks.append(text)
    return "".join(chunks).strip()


def _parse_json_response(text: str) -> dict[str, Any]:
    stripped_text = _strip_markdown_json_fence(text)
    try:
        parsed = json.loads(stripped_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {stripped_text}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed


def _strip_markdown_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped
