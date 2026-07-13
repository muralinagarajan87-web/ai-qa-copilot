from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from agents.base.schemas import ArtifactKind, ArtifactRef, WorkflowState


class WorkflowRun(BaseModel):
    run_id: str
    state: WorkflowState
    artifacts: dict[ArtifactKind, ArtifactRef] = Field(default_factory=dict)
    revision_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
