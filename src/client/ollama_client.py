"""Ollama HTTP API 래퍼 — JSON Schema 강제 + vision 입력 + 결정론 옵션."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 600  # seconds — vision 입력 큰 PDF에 대비


@dataclass(frozen=True)
class OllamaResult:
    """Ollama 호출 1회 결과."""
    response_text: str
    model: str
    model_digest: str          # `ollama show` 의 id (재현성 키)
    prompt_eval_count: int     # 입력 토큰 (prompt + image)
    eval_count: int            # 출력 토큰
    eval_duration_ns: int
    total_duration_ns: int
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def eval_ms(self) -> int:
        return self.eval_duration_ns // 1_000_000

    @property
    def total_ms(self) -> int:
        return self.total_duration_ns // 1_000_000


class OllamaClient:
    """Ollama generate API 래퍼.

    사용 예:
        client = OllamaClient(model="gemma4:31b", seed=42, temperature=0.1)
        result = client.generate(prompt="...", json_schema={...})
        result_vision = client.generate(prompt="...", json_schema={...}, images=[b64_png, ...])
    """

    def __init__(
        self,
        model: str = "gemma4:31b",
        base_url: str = DEFAULT_BASE_URL,
        seed: int = 42,
        temperature: float = 0.1,
        num_predict: int = 4096,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.seed = seed
        self.temperature = temperature
        self.num_predict = num_predict
        self.timeout = timeout
        self._digest: str | None = None

    def ping(self) -> str:
        """서버 응답 + 버전 확인."""
        r = requests.get(f"{self.base_url}/api/version", timeout=5)
        r.raise_for_status()
        return r.json().get("version", "unknown")

    def get_model_digest(self) -> str:
        """모델 정체성 hash (재현성 로깅용). 캐시됨."""
        if self._digest is not None:
            return self._digest
        r = requests.post(f"{self.base_url}/api/show", json={"name": self.model}, timeout=10)
        r.raise_for_status()
        data = r.json()
        # Ollama는 모델 hash를 details.digest 또는 model_info 등에 둘 수 있음
        self._digest = data.get("digest") or data.get("details", {}).get("digest") or "unknown"
        return self._digest

    def generate(
        self,
        prompt: str,
        json_schema: dict[str, Any] | None = None,
        images: list[str] | None = None,
        *,
        seed: int | None = None,
        temperature: float | None = None,
        num_predict: int | None = None,
    ) -> OllamaResult:
        """Ollama /api/generate 호출.

        Args:
            prompt: 본 프롬프트
            json_schema: JSON Schema (있으면 grammar 수준에서 강제)
            images: base64 PNG 리스트 (vision 입력)
            seed/temperature/num_predict: 호출별 override

        Returns:
            OllamaResult — 응답 텍스트 + 메타
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "seed": seed if seed is not None else self.seed,
                "num_predict": num_predict if num_predict is not None else self.num_predict,
            },
        }
        if json_schema is not None:
            payload["format"] = json_schema
        if images:
            payload["images"] = images

        logger.info(
            f"[ollama] model={self.model} seed={payload['options']['seed']} "
            f"temp={payload['options']['temperature']} images={len(images) if images else 0} "
            f"schema={'yes' if json_schema else 'no'}"
        )
        r = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return OllamaResult(
            response_text=data["response"],
            model=data.get("model", self.model),
            model_digest=self.get_model_digest(),
            prompt_eval_count=data.get("prompt_eval_count", 0),
            eval_count=data.get("eval_count", 0),
            eval_duration_ns=data.get("eval_duration", 0),
            total_duration_ns=data.get("total_duration", 0),
            raw=data,
        )
