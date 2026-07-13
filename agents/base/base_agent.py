from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Generic

import yaml

from agents.base.agent_interface import AgentInputT, AgentOutputT
from agents.base.schemas import ArtifactKind, ValidationResult, WorkflowContext
from events.event_bus import EventBusProtocol, WorkflowEvent
from llm.pricing import estimate_cost_usd
from llm.provider import LLMProvider, LLMResponse
from services.artifact_manager import ArtifactManager

logger = logging.getLogger("agent")


class BaseAgent(ABC, Generic[AgentInputT, AgentOutputT]):
    """Shared scaffolding every concrete agent gets for free: config/prompt
    loading, LLM + ArtifactManager access, memory read/write, and
    execute()/retry() with identical event-publishing and backoff behavior.

    Concrete agents implement `build_input`, `_run`, `validate`, and
    `explain` -- the domain-specific pieces. They never re-implement retry
    logic, prompt loading, or event publishing.
    """

    name: str
    output_kind: ArtifactKind

    def __init__(
        self,
        *,
        agent_dir: Path,
        llm: LLMProvider,
        event_bus: EventBusProtocol,
        artifact_manager: ArtifactManager,
        max_retries: int = 2,
    ):
        if not hasattr(self, "name") or not hasattr(self, "output_kind"):
            raise NotImplementedError(f"{type(self).__name__} must set class attributes 'name' and 'output_kind'")
        self.agent_dir = agent_dir
        self.llm = llm
        self.event_bus = event_bus
        self.artifact_manager = artifact_manager
        self.max_retries = max_retries
        self.config = self._load_config()
        self.prompt_version = self.config.get("prompt_version", "v1")
        self.prompt = self._load_prompt()

    def _load_config(self) -> dict:
        return yaml.safe_load((self.agent_dir / "config.yaml").read_text()) or {}

    def _load_prompt(self) -> str:
        return (self.agent_dir / "prompts" / f"{self.prompt_version}.md").read_text()

    def _load_prompt_file(self, filename: str) -> str:
        """For agents that need more than one system prompt (e.g. a
        multi-stage pipeline) -- `self.prompt`/`self.prompt_version` above
        cover the single-prompt case every other agent uses.
        """
        return (self.agent_dir / "prompts" / filename).read_text()

    @abstractmethod
    def build_input(self, context: WorkflowContext) -> AgentInputT: ...

    def execute(self, input: AgentInputT, context: WorkflowContext) -> AgentOutputT:
        self.event_bus.publish(WorkflowEvent(type=f"{self.name}.started", run_id=context.run_id, payload={}))
        try:
            output = self._run(input, context)
        except Exception as error:  # noqa: BLE001 -- deliberately broad: any failure triggers the retry path
            logger.warning("%s failed on first attempt: %s", self.name, error)
            try:
                output = self.retry(input, context, error)
            except Exception as final_error:  # noqa: BLE001
                self._record_history(context, status="failed", detail=str(final_error))
                raise
            else:
                self._record_history(context, status="recovered", detail=f"succeeded on retry after: {error}")
                return output
        self._record_history(context, status="success")
        return output

    def retry(self, input: AgentInputT, context: WorkflowContext, error: Exception) -> AgentOutputT:
        last_error = error
        for attempt in range(1, self.max_retries + 1):
            self.event_bus.publish(
                WorkflowEvent(
                    type=f"{self.name}.retry",
                    run_id=context.run_id,
                    payload={"attempt": attempt, "error": str(last_error)},
                )
            )
            time.sleep(min(2**attempt, 10))
            try:
                return self._run(input, context)
            except Exception as retry_error:  # noqa: BLE001
                last_error = retry_error
        raise RuntimeError(f"{self.name} failed after {self.max_retries} retries") from last_error

    @abstractmethod
    def _run(self, input: AgentInputT, context: WorkflowContext) -> AgentOutputT:
        """Single-attempt generation. Raise on failure -- execute()/retry()
        handle the retry loop; this method should not catch its own errors.
        """
        ...

    @abstractmethod
    def validate(self, output: AgentOutputT) -> ValidationResult: ...

    @abstractmethod
    def explain(self, output: AgentOutputT) -> str: ...

    def read_llm_calls(self, run_id: str | None = None) -> list[dict]:
        """Public accessor for this agent's LLM telemetry (see
        _record_llm_call) -- used by the API layer to expose per-run cost
        and latency without reaching into agent internals directly.
        """
        calls = self._read_memory("llm_calls.json")
        if not isinstance(calls, list):
            return []
        if run_id is None:
            return calls
        return [call for call in calls if call.get("run_id") == run_id]

    def _read_memory(self, filename: str) -> dict | list:
        path = self.agent_dir / "memory" / filename
        return json.loads(path.read_text()) if path.exists() else {}

    def _write_memory(self, filename: str, data: dict | list) -> None:
        path = self.agent_dir / "memory" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))

    def _record_history(self, context: WorkflowContext, *, status: str, detail: str | None = None) -> None:
        """Generic per-agent audit trail (agents/<name>/memory/history.json) --
        every agent gets this for free rather than each one reimplementing it.
        """
        history = self._read_memory("history.json")
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "run_id": context.run_id,
                "status": status,
                "detail": detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._write_memory("history.json", history)

    def _record_llm_call(
        self, response: LLMResponse, *, context: WorkflowContext, temperature: float, purpose: str = "generate"
    ) -> None:
        """Per-call LLM telemetry (agents/<name>/memory/llm_calls.json) --
        separate from _record_history's coarse execution status, since one
        agent execution can involve multiple LLM calls (e.g. a multi-stage
        pipeline) and this is cost/performance data, not pass/fail status.
        Call this explicitly right after `self.llm.generate(...)`.
        """
        provider_name = getattr(self.llm, "provider_name", type(self.llm).__name__)
        raw_cost = estimate_cost_usd(provider_name, response.model, response.usage)
        cost_usd = round(raw_cost, 6) if raw_cost is not None else None

        record = {
            "run_id": context.run_id,
            "agent": self.name,
            "purpose": purpose,
            "provider": provider_name,
            "model": response.model,
            "prompt_version": self.prompt_version,
            "temperature": temperature,
            "tokens": response.usage.model_dump(),
            "latency_ms": round(response.latency_ms, 1),
            "cost_usd": cost_usd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        calls = self._read_memory("llm_calls.json")
        if not isinstance(calls, list):
            calls = []
        calls.append(record)
        self._write_memory("llm_calls.json", calls)

        self.event_bus.publish(WorkflowEvent(type=f"{self.name}.llm_call", run_id=context.run_id, payload=record))
