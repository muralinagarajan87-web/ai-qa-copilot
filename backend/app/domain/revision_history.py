from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from agents.base.schemas import ArtifactKind, ArtifactRef, ReviewComment, WorkflowState
from services.artifact_manager import ArtifactManager


class CommentResolution(BaseModel):
    comment: ReviewComment
    resolved: bool


class RevisionEntry(BaseModel):
    run_id: str
    iteration: int
    code_ref: ArtifactRef
    review_ref: ArtifactRef
    comments: list[ReviewComment]
    resolutions_from_previous: list[CommentResolution] = Field(default_factory=list)
    outcome: Literal["approved", "revision_needed", "revision_limit_exceeded"]
    timestamp: datetime


class RevisionHistory(BaseModel):
    run_id: str
    entries: list[RevisionEntry]
    final_outcome: Literal["completed", "revision_limit_exceeded", "rejected", "in_progress"]


_STATE_TO_OUTCOME: dict[WorkflowState, str] = {
    WorkflowState.COMPLETED: "completed",
    WorkflowState.REVISION_LIMIT_EXCEEDED: "revision_limit_exceeded",
    WorkflowState.REJECTED: "rejected",
}


def _identity(comment: ReviewComment) -> tuple[str, str]:
    """(file, rule) is the stable identity of "this class of problem in this
    file" -- not (file, line), since a fix commonly shifts every subsequent
    line in the file.
    """
    return (comment.file, comment.rule)


class RevisionHistoryBuilder:
    """Builds the demo audit trail by pairing versioned PLAYWRIGHT_CODE and
    REVIEW_COMMENTS artifacts per run -- no separate log is kept, so this
    can never drift from the artifacts it describes (docs/architecture/design.md SS11).

    Resolution status is judged here by diffing consecutive Reviewer
    outputs, not by anything the Automation Agent claims to have fixed --
    an agent should not grade its own homework.
    """

    def __init__(self, artifact_manager: ArtifactManager):
        self.artifact_manager = artifact_manager

    def build(self, run_id: str, *, max_attempts: int, run_state: WorkflowState | None = None) -> RevisionHistory:
        code_versions = self.artifact_manager.list_versions(run_id, ArtifactKind.PLAYWRIGHT_CODE)
        review_versions = self.artifact_manager.list_versions(run_id, ArtifactKind.REVIEW_COMMENTS)

        entries: list[RevisionEntry] = []
        previous_comments: list[ReviewComment] = []

        for iteration, (code_ref, review_ref) in enumerate(zip(code_versions, review_versions), start=1):
            review_data = json.loads(self.artifact_manager.load(review_ref))
            comments = [ReviewComment(**c) for c in review_data.get("comments", [])]
            approved = bool(review_data.get("approved", False))

            current_identities = {_identity(c) for c in comments}
            resolutions = [
                CommentResolution(comment=prev, resolved=_identity(prev) not in current_identities)
                for prev in previous_comments
            ]

            if approved:
                outcome = "approved"
            elif iteration >= max_attempts:
                outcome = "revision_limit_exceeded"
            else:
                outcome = "revision_needed"

            entries.append(
                RevisionEntry(
                    run_id=run_id,
                    iteration=iteration,
                    code_ref=code_ref,
                    review_ref=review_ref,
                    comments=comments,
                    resolutions_from_previous=resolutions,
                    outcome=outcome,
                    timestamp=self.artifact_manager.saved_at(review_ref),
                )
            )
            previous_comments = comments

        if run_state is not None:
            final_outcome = _STATE_TO_OUTCOME.get(run_state, "in_progress")
        elif entries and entries[-1].outcome == "revision_limit_exceeded":
            final_outcome = "revision_limit_exceeded"
        else:
            final_outcome = "in_progress"

        return RevisionHistory(run_id=run_id, entries=entries, final_outcome=final_outcome)
