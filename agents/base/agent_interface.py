from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from agents.base.schemas import ArtifactKind, ValidationResult, WorkflowContext

AgentInputT = TypeVar("AgentInputT", bound=BaseModel)
AgentOutputT = TypeVar("AgentOutputT", bound=BaseModel)


@runtime_checkable
class AgentProtocol(Protocol[AgentInputT, AgentOutputT]):
    """Every agent -- regardless of what it does internally -- exposes this
    exact surface. It is what lets the Orchestrator stay free of business
    logic: it only ever calls these five members, never anything specific
    to test cases, Playwright code, or review rules.
    """

    name: str
    output_kind: ArtifactKind

    def build_input(self, context: WorkflowContext) -> AgentInputT:
        """Assemble this agent's typed input from prior artifacts in `context`.

        This is where per-agent knowledge of "which artifact, which fields"
        lives -- deliberately kept out of the Orchestrator, which only knows
        artifact kinds generically.
        """
        ...

    def execute(self, input: AgentInputT, context: WorkflowContext) -> AgentOutputT: ...

    def validate(self, output: AgentOutputT) -> ValidationResult: ...

    def explain(self, output: AgentOutputT) -> str: ...

    def retry(self, input: AgentInputT, context: WorkflowContext, error: Exception) -> AgentOutputT:
        """Re-attempt after a transient failure (LLM timeout, malformed
        response). Not used for applying Reviewer feedback -- that is a
        fresh `execute()` call with review_comments populated in `context`.
        """
        ...
