from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from agents.base.schemas import WorkflowState


class Transition(BaseModel):
    from_state: WorkflowState = Field(alias="from")
    agent: str
    on_success: WorkflowState | None = None
    on_approved: WorkflowState | None = None
    on_rejected: WorkflowState | None = None


class RevisionPolicy(BaseModel):
    max_attempts: int = 3
    on_limit_exceeded: WorkflowState = WorkflowState.REVISION_LIMIT_EXCEEDED


class WorkflowConfig(BaseModel):
    """Typed view of configuration/workflow.yaml. States with no matching
    transition (awaiting_approval, completed, rejected,
    revision_limit_exceeded) are human-gated or terminal by construction --
    the engine just stops walking the table when transition_for() is None.
    """

    transitions: list[Transition]
    revision: RevisionPolicy = RevisionPolicy()

    def transition_for(self, state: WorkflowState) -> Transition | None:
        return next((t for t in self.transitions if t.from_state == state), None)


def load_workflow_config(path: Path) -> WorkflowConfig:
    raw = yaml.safe_load(path.read_text())
    return WorkflowConfig.model_validate(raw)
