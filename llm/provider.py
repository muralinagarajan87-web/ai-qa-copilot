from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMResponse(BaseModel):
    text: str
    model: str
    parsed: dict | None = None
    usage: TokenUsage = TokenUsage()
    latency_ms: float = 0.0


class LLMProvider(Protocol):
    """Every model backend (Ollama and Groq today, OpenAI/Claude as
    structural stubs for later) implements this. Agents depend on
    LLMProvider, never on a concrete client -- see llm/router.py and
    configuration/models.yaml.
    """

    provider_name: str

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse: ...

    def embed(self, text: str) -> list[float]: ...
