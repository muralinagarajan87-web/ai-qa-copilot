from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agents.base.schemas import ArtifactRef


class TestCaseGeneratorInput(BaseModel):
    run_id: str
    source_document: ArtifactRef
    module_hint: str | None = None


# --- Stage A: requirement extraction ------------------------------------
#
# Requirement IDs are assigned by the agent (REQ-001, REQ-002, ...), never
# by the LLM -- letting the model invent IDs risks the same requirement
# getting labeled differently across test cases, which breaks the whole
# point of a traceability matrix. Extraction happens as its own LLM call so
# the requirement list is stable and de-duplicated before any test case
# generation references it.


class ExtractedRequirement(BaseModel):
    description: str
    source_reference: str | None = None
    module: str


class ExtractedRequirements(BaseModel):
    requirements: list[ExtractedRequirement]


class Requirement(ExtractedRequirement):
    requirement_id: str


# --- Stage B: test case generation from requirements ---------------------
#
# requirement_description / source_reference / module are deliberately NOT
# part of what the LLM produces per test case -- they are looked up from the
# Requirement list by requirement_id after generation. Asking the model to
# repeat them verbatim for every test case would just be another chance for
# it to drift/paraphrase inconsistently; a lookup can't drift.


class AutomationAssessment(BaseModel):
    candidate: bool
    reason: str


class GeneratedTestCase(BaseModel):
    requirement_id: str
    feature: str | None = None
    description: str
    test_objective: str
    priority: Literal["P0", "P1", "P2", "P3"]
    severity: Literal["critical", "major", "minor", "trivial"]
    preconditions: list[str]
    test_data: dict[str, str] = Field(default_factory=dict)
    steps: list[str]
    expected_result: str
    test_type: Literal["functional", "regression", "smoke", "edge_case", "negative"]
    automation: AutomationAssessment
    risk: Literal["low", "medium", "high"]
    confidence: Literal["high", "medium", "low"]


class GeneratedTestCases(BaseModel):
    test_cases: list[GeneratedTestCase]
    coverage_notes: str | None = None


class TestCase(GeneratedTestCase):
    test_id: str
    requirement_description: str
    source_reference: str | None = None
    module: str


class TestCaseGeneratorOutput(BaseModel):
    run_id: str
    prompt_version: str
    requirements: list[Requirement]
    test_cases: list[TestCase]
    coverage_notes: str | None = None
