from __future__ import annotations

import json
import os
import time

import anthropic
from pydantic import BaseModel

from llm.provider import LLMResponse, TokenUsage


class ClaudeRateLimitError(RuntimeError):
    """Raised on Anthropic's typed RateLimitError, with the message surfaced
    directly instead of letting a generic exception propagate as an opaque
    500 further up the stack (same reasoning as GroqRateLimitError).
    """


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


class ClaudeProvider:
    """Anthropic Claude via the official `anthropic` Python SDK -- a third
    generation provider alongside Groq and Ollama behind the same
    LLMProvider interface, selectable via configuration/models.yaml with no
    agent code changes.

    Structured output is prompt-based (JSON Schema embedded in the system
    prompt, response parsed as JSON) -- deliberately NOT Claude's native
    `output_config.format` strict-schema mode. That mode requires every
    object in the schema to set `additionalProperties: false`, which is
    incompatible with this project's open key/value fields (e.g.
    TestCase.test_data: dict[str, str]) without reshaping the data model
    just for one provider. Keeping all three providers on the same
    prompt-based strategy also means one consistent retry-on-malformed-JSON
    path in BaseAgent, rather than Claude behaving subtly differently from
    Groq/Ollama.

    Requires ANTHROPIC_API_KEY in the environment (see .env.example).
    Claude has no embeddings endpoint -- embeddings always route through a
    dedicated embedding-capable provider (Ollama by default); see
    llm/router.py get_embedding_provider().
    """

    provider_name = "claude"

    def __init__(self, model: str, *, max_tokens: int = 8000, timeout: float = 120.0):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your Anthropic API "
                "key, or switch configuration/models.yaml 'default.provider' to 'groq' or 'ollama'."
            )
        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

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
                f"exactly, with no other text before or after it, and no markdown code fences:\n{schema_hint}"
            ).strip()

        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        started = time.monotonic()
        try:
            response = self._client.messages.create(**kwargs)
        except anthropic.RateLimitError as error:
            raise ClaudeRateLimitError(f"Claude rate limit hit (429): {error}") from error
        latency_ms = (time.monotonic() - started) * 1000

        text = "".join(block.text for block in response.content if block.type == "text")

        parsed = None
        if response_schema is not None:
            parsed = json.loads(_strip_code_fences(text))

        usage = TokenUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )
        return LLMResponse(text=text, model=self.model, parsed=parsed, usage=usage, latency_ms=latency_ms)

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError(
            "ClaudeProvider has no embeddings endpoint -- embeddings always route through the "
            "dedicated embedding provider (configuration/models.yaml 'embedding' section) via "
            "LLMRouter.get_embedding_provider(), regardless of the generation provider in use."
        )
