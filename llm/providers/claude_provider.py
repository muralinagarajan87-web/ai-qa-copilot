from __future__ import annotations

from pydantic import BaseModel

from llm.provider import LLMResponse


class ClaudeProvider:
    """Structural stub satisfying LLMProvider -- see openai_provider.py for
    rationale. Not used while this project runs local-only via Ollama.
    """

    def __init__(self, model: str, **_: object):
        self.model = model

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError("ClaudeProvider is a structural stub -- this project runs local-only via Ollama")

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError("ClaudeProvider is a structural stub -- this project runs local-only via Ollama")
