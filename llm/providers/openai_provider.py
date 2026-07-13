from __future__ import annotations

from pydantic import BaseModel

from llm.provider import LLMResponse


class OpenAIProvider:
    """Structural stub satisfying LLMProvider -- this project runs
    local-only via Ollama (see docs/architecture/design.md constraints).
    Exists so `llm/router.py` and `configuration/models.yaml` can name
    "openai" as a provider without a code change, if a cloud-model
    comparison is ever explicitly required.
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
        raise NotImplementedError("OpenAIProvider is a structural stub -- this project runs local-only via Ollama")

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError("OpenAIProvider is a structural stub -- this project runs local-only via Ollama")
