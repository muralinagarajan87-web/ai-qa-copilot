from __future__ import annotations

from pathlib import Path

import yaml

from llm.provider import LLMProvider
from llm.providers.claude_provider import ClaudeProvider
from llm.providers.groq_provider import GroqProvider
from llm.providers.ollama_provider import OllamaProvider
from llm.providers.openai_provider import OpenAIProvider

_PROVIDERS = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "groq": GroqProvider,
}

_EMBEDDING_CACHE_KEY = "__embedding__"


class LLMRouter:
    """Resolves which LLMProvider (and which model) an agent gets, purely
    from configuration/models.yaml. One provider instance per agent name,
    cached for the process lifetime.

    Embeddings are resolved separately via get_embedding_provider() rather
    than through an agent's generation provider, since not every provider
    (Groq, notably) offers an embeddings endpoint -- the embedding model is
    independently configured under the 'embedding' key.
    """

    def __init__(self, config_path: Path):
        self._config = yaml.safe_load(config_path.read_text()) or {}
        self._embedding_config = self._config.get("embedding", {"provider": "ollama", "model": "nomic-embed-text"})
        self._cache: dict[str, LLMProvider] = {}

    def get_provider(self, agent_name: str) -> LLMProvider:
        if agent_name in self._cache:
            return self._cache[agent_name]

        entry = (self._config.get("agents") or {}).get(agent_name, self._config["default"])
        provider = self._build(entry)
        self._cache[agent_name] = provider
        return provider

    def get_embedding_provider(self) -> LLMProvider:
        if _EMBEDDING_CACHE_KEY in self._cache:
            return self._cache[_EMBEDDING_CACHE_KEY]
        provider = self._build(self._embedding_config)
        self._cache[_EMBEDDING_CACHE_KEY] = provider
        return provider

    def _build(self, entry: dict) -> LLMProvider:
        provider_cls = _PROVIDERS[entry["provider"]]
        kwargs: dict = {"model": entry["model"]}
        if entry["provider"] == "ollama":
            kwargs["embedding_model"] = self._embedding_config.get("model", "nomic-embed-text")
        if "max_tokens" in entry:
            kwargs["max_tokens"] = entry["max_tokens"]
        return provider_cls(**kwargs)
