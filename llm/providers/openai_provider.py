from __future__ import annotations

from pydantic import BaseModel

from llm.provider import LLMResponse


class OpenAIProvider:
    """Structural stub satisfying LLMProvider. Exists so `llm/router.py` and
    `configuration/models.yaml` can name "openai" as a provider without a
    code change, if a cloud-model comparison is ever explicitly required.
    Groq and Ollama are the two implemented, supported providers today.
    """

    provider_name = "openai"

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
        raise NotImplementedError("OpenAIProvider is a structural stub -- not yet implemented")

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError("OpenAIProvider is a structural stub -- not yet implemented")
