from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from agents.base.schemas import ArtifactKind, WorkflowState
from services.artifact_manager import ArtifactManager

# The only test types this agent actually generates and reasons about.
# Coverage is reported strictly against this list -- not against
# Security/Accessibility/Performance/API, which this agent has no real basis
# to assess from a plain PRD. A checkbox for a capability that doesn't exist
# would be worse than no checkbox at all.
_COVERAGE_TEST_TYPES = ["functional", "negative", "edge_case", "regression", "smoke"]


class TraceabilityRow(BaseModel):
    requirement_id: str
    requirement_description: str
    module: str
    test_case_ids: list[str]
    coverage: dict[str, bool]
    automation_status: Literal["pending", "generated"]
    reviewer_status: Literal["pending", "approved", "changes_requested", "limit_exceeded"]


class TraceabilityMatrix(BaseModel):
    run_id: str
    rows: list[TraceabilityRow]


class TraceabilityMatrixBuilder:
    """Requirement -> Test Case -> Automation -> Reviewer, computed from the
    same versioned artifacts as everything else (docs/architecture/design.md
    SS11's "no separate source of truth" principle applies here too).

    Automation/Reviewer status is currently workflow-stage-wide (has code
    been generated at all? has the latest review approved?) rather than
    per-test-case, since Reviewer comments are file-scoped, not
    test-case-scoped. Once the Reviewer Agent exists, this can be refined to
    per-row status if review comments start carrying test-case references.
    """

    def __init__(self, artifact_manager: ArtifactManager):
        self.artifact_manager = artifact_manager

    def build(self, run_id: str, *, run_state: WorkflowState) -> TraceabilityMatrix:
        test_case_versions = self.artifact_manager.list_versions(run_id, ArtifactKind.TEST_CASES)
        if not test_case_versions:
            return TraceabilityMatrix(run_id=run_id, rows=[])

        test_case_data = json.loads(self.artifact_manager.load(test_case_versions[-1]))
        requirements = test_case_data.get("requirements", [])
        test_cases = test_case_data.get("test_cases", [])

        test_case_ids_by_requirement: dict[str, list[str]] = {}
        test_types_by_requirement: dict[str, set[str]] = {}
        for test_case in test_cases:
            requirement_id = test_case["requirement_id"]
            test_case_ids_by_requirement.setdefault(requirement_id, []).append(test_case["test_id"])
            test_types_by_requirement.setdefault(requirement_id, set()).add(test_case["test_type"])

        automation_status = self._automation_status(run_id)
        reviewer_status = self._reviewer_status(run_id, run_state)

        rows = [
            TraceabilityRow(
                requirement_id=requirement["requirement_id"],
                requirement_description=requirement["description"],
                module=requirement["module"],
                test_case_ids=test_case_ids_by_requirement.get(requirement["requirement_id"], []),
                coverage={
                    test_type: test_type in test_types_by_requirement.get(requirement["requirement_id"], set())
                    for test_type in _COVERAGE_TEST_TYPES
                },
                automation_status=automation_status,
                reviewer_status=reviewer_status,
            )
            for requirement in requirements
        ]
        return TraceabilityMatrix(run_id=run_id, rows=rows)

    def _automation_status(self, run_id: str) -> Literal["pending", "generated"]:
        has_code = bool(self.artifact_manager.list_versions(run_id, ArtifactKind.PLAYWRIGHT_CODE))
        return "generated" if has_code else "pending"

    def _reviewer_status(
        self, run_id: str, run_state: WorkflowState
    ) -> Literal["pending", "approved", "changes_requested", "limit_exceeded"]:
        if run_state == WorkflowState.REVISION_LIMIT_EXCEEDED:
            return "limit_exceeded"
        review_versions = self.artifact_manager.list_versions(run_id, ArtifactKind.REVIEW_COMMENTS)
        if not review_versions:
            return "pending"
        latest_review = json.loads(self.artifact_manager.load(review_versions[-1]))
        return "approved" if latest_review.get("approved") else "changes_requested"
