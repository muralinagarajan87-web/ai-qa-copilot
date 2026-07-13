from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    PRD_RECEIVED = "prd_received"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    UNDER_REVIEW = "under_review"
    REVISION_NEEDED = "revision_needed"
    COMPLETED = "completed"
    REJECTED = "rejected"
    REVISION_LIMIT_EXCEEDED = "revision_limit_exceeded"


class ArtifactKind(str, Enum):
    PRD = "prd"
    TEST_CASES = "test_cases"
    PLAYWRIGHT_CODE = "playwright_code"
    REVIEW_COMMENTS = "review_comments"


class ArtifactRef(BaseModel):
    run_id: str
    kind: ArtifactKind
    version: int
    path: str


class ReviewComment(BaseModel):
    """Shared here (rather than under reviewer_agent/) because WorkflowContext
    carries review comments across every agent that might need them."""

    file: str
    line: int | None = None
    rule: str
    severity: Literal["blocker", "major", "minor", "info"]
    message: str
    suggested_fix: str | None = None


class WorkflowContext(BaseModel):
    run_id: str
    state: WorkflowState
    previous_outputs: dict[ArtifactKind, ArtifactRef] = Field(default_factory=dict)
    review_comments: list[ReviewComment] = Field(default_factory=list)
    revision_count: int = 0


class ValidationResult(BaseModel):
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
