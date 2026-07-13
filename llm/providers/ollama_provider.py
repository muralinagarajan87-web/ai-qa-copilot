from __future__ import annotations

import json
import time

import httpx
from pydantic import BaseModel

from llm.provider import LLMResponse, TokenUsage


class OllamaProvider:
    """Talks to a local Ollama daemon over HTTP -- no cloud dependency.
    When `response_schema` is given, the schema's JSON Schema is passed as
    Ollama's `format` so the model is constrained to structured output,
    which is then parsed into `LLMResponse.parsed`.

    Kept as the fully-local, offline-capable provider (see
    docs/architecture/design.md and configuration/models.yaml) -- Groq is
    the default for speed, but Ollama must still work correctly on its own
    for that fallback to mean anything. Schema-constrained decoding on
    modest local hardware measurably takes minutes, not seconds, so the
    default timeout here is generous; raise it further via the `timeout`
    kwarg for larger models or larger outputs.
    """

    provider_name = "ollama"

    def __init__(
        self,
        model: str,
        *,
        embedding_model: str = "nomic-embed-text",
        host: str = "http://localhost:11434",
        timeout: float = 300.0,
    ):
        self.model = model
        self.embedding_model = embedding_model
        self.host = host.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system is not None:
            payload["system"] = system
        if response_schema is not None:
            payload["format"] = response_schema.model_json_schema()

        started = time.monotonic()
        response = self._client.post(f"{self.host}/api/generate", json=payload)
        latency_ms = (time.monotonic() - started) * 1000
        response.raise_for_status()
        data = response.json()
        text = data.get("response", "")

        parsed = json.loads(text) if response_schema is not None else None
        usage = TokenUsage(
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            total_tokens=(
                (data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0)
                if data.get("prompt_eval_count") is not None or data.get("eval_count") is not None
                else None
            ),
        )
        return LLMResponse(text=text, model=self.model, parsed=parsed, usage=usage, latency_ms=latency_ms)

    def embed(self, text: str) -> list[float]:
        response = self._client.post(
            f"{self.host}/api/embeddings",
            json={"model": self.embedding_model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]
