from __future__ import annotations

from typing import Callable

from agents.base.agent_interface import AgentProtocol


class AgentNotRegisteredError(KeyError):
    pass


class AgentRegistry:
    """The only thing the Orchestrator knows about agents: their string
    names. `configuration/agents.yaml` drives what gets registered here at
    startup (see backend/app/core/container.py) -- adding a 10th agent is a
    YAML entry plus the agent module, with zero changes to the Orchestrator.
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], AgentProtocol]] = {}

    def register(self, name: str, factory: Callable[[], AgentProtocol]) -> None:
        self._factories[name] = factory

    def get(self, name: str) -> AgentProtocol:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise AgentNotRegisteredError(
                f"No agent registered under '{name}'. Registered: {sorted(self._factories)}"
            ) from exc
        return factory()

    def list_agents(self) -> list[str]:
        return sorted(self._factories)
