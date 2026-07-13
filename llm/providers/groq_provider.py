from __future__ import annotations

import json
import os
import time

import httpx
from pydantic import BaseModel

from llm.provider import LLMResponse, TokenUsage


class GroqProvider:
    """Groq Cloud (OpenAI-compatible chat completions API) -- the default
    provider for development and live demos because of its low latency
    compared to local inference on modest hardware. Ollama remains fully
    supported for offline/local-only deployments; switching back is a
    configuration/models.yaml change only, no agent code changes required.

    Requires GROQ_API_KEY in the environment (see .env.example). Groq has no
    embeddings endpoint -- embeddings always route through a dedicated
    embedding-capable provider (Ollama by default) regardless of which
    provider is generating text; see llm/router.py get_embedding_provider().
    """

    provider_name = "groq"

    def __init__(
        self,
        model: str,
        *,
        host: str = "https://api.groq.com/openai/v1",
        timeout: float = 60.0,
        max_tokens: int = 8000,
    ):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your Groq API key, "
                "or switch configuration/models.yaml 'default.provider' back to 'ollama'."
            )
        self.model = model
        self.host = host.rstrip("/")
        self.max_tokens = max_tokens
        self._client = httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        system_prompt = system or ""
        if response_schema is not None:
            schema_hint = json.dumps(response_schema.model_json_schema())
            system_prompt = (
                f"{system_prompt}\n\nRespond with a single JSON object that matches this JSON Schema "
                f"exactly, with no other text before or after it:\n{schema_hint}"
            ).strip()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        if response_schema is not None:
            payload["response_format"] = {"type": "json_object"}

        started = time.monotonic()
        response = self._client.post(f"{self.host}/chat/completions", json=payload)
        latency_ms = (time.monotonic() - started) * 1000
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        text = choice["message"]["content"]

        if choice.get("finish_reason") == "length":
            raise RuntimeError(
                f"Groq response was truncated at max_tokens={self.max_tokens} before finishing -- "
                "the requested output was too large. Increase GroqProvider's max_tokens."
            )

        parsed = json.loads(text) if response_schema is not None else None
        raw_usage = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=raw_usage.get("prompt_tokens"),
            completion_tokens=raw_usage.get("completion_tokens"),
            total_tokens=raw_usage.get("total_tokens"),
        )
        return LLMResponse(text=text, model=self.model, parsed=parsed, usage=usage, latency_ms=latency_ms)

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError(
            "GroqProvider has no embeddings endpoint -- embeddings always route through the "
            "dedicated embedding provider (configuration/models.yaml 'embedding' section) via "
            "LLMRouter.get_embedding_provider(), regardless of the generation provider in use."
        )
