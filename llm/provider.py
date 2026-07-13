from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    model: str
    parsed: dict | None = None


class LLMProvider(Protocol):
    """Every model backend (Ollama today, OpenAI/Claude as structural stubs
    for later) implements this. Agents depend on LLMProvider, never on a
    concrete client -- see llm/router.py and configuration/models.yaml.
    """

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse: ...

    def embed(self, text: str) -> list[float]: ...
