from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from agents.base.schemas import ArtifactRef


class TestCaseGeneratorInput(BaseModel):
    run_id: str
    source_document: ArtifactRef
    module_hint: str | None = None


class GeneratedTestCase(BaseModel):
    """What we ask the LLM to produce -- deliberately excludes test_id.
    IDs are assigned deterministically by the agent after generation rather
    than trusted to the model, so they are always unique and stable.
    """

    module: str
    priority: Literal["P0", "P1", "P2", "P3"]
    description: str
    preconditions: list[str]
    steps: list[str]
    expected_result: str
    test_type: Literal["functional", "regression", "smoke", "edge_case", "negative"]
    automation_candidate: bool
    risk: Literal["low", "medium", "high"]


class GeneratedTestCases(BaseModel):
    test_cases: list[GeneratedTestCase]
    coverage_notes: str | None = None


class TestCase(GeneratedTestCase):
    test_id: str


class TestCaseGeneratorOutput(BaseModel):
    run_id: str
    test_cases: list[TestCase]
    coverage_notes: str | None = None
