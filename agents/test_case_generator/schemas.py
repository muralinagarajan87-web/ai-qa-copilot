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
#
# requirement_type drives Stage B's decomposition depth: "validation"
# requirements get deep boundary/format scenario decomposition, while
# "ui_behavior"/"business_rule" get the minimal meaningful set. This is what
# makes coverage scenario-driven instead of a flat "one or more per
# requirement" instruction.


class RequirementGap(BaseModel):
    topic: str
    description: str
    recommendation: str


class ExtractedRequirement(BaseModel):
    description: str
    source_reference: str | None = None
    module: str
    requirement_type: Literal[
        "functional", "business_rule", "validation", "ui_behavior", "security", "accessibility", "integration", "performance"
    ]


class ExtractedRequirements(BaseModel):
    """Stage A output. ambiguities/gaps/assumptions are the model reflecting
    on the PRD itself, not on the requirements it extracted -- this is what
    turns the agent from a pure test-case generator into a lightweight
    requirements-quality reviewer as well.
    """

    requirements: list[ExtractedRequirement]
    ambiguities: list[str] = Field(default_factory=list)
    gaps: list[RequirementGap] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class Requirement(ExtractedRequirement):
    requirement_id: str


# --- Stage B: test case generation from requirements ---------------------
#
# requirement_description / source_reference / module are deliberately NOT
# part of what the LLM produces per test case -- they are looked up from the
# Requirement list by requirement_id after generation. Asking the model to
# repeat them verbatim for every test case would just be another chance for
# it to drift/paraphrase inconsistently; a lookup can't drift.


class TestStep(BaseModel):
    action: str
    expected: str


class AutomationHints(BaseModel):
    """Advisory hints for the future Automation Agent -- semantic element
    names and intended Playwright actions/assertions, NOT final selectors.
    No real DOM or design-system component library exists at test-case-
    generation time; the Automation Agent is expected to resolve these
    against real Page Objects (via the RAG pom_library lookup once
    knowledge/ ships) rather than trust them as literal locators.
    """

    page_object: str | None = None
    locators: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    assertions: list[str] = Field(default_factory=list)
    complexity: Literal["low", "medium", "high"] | None = None
    estimated_minutes: int | None = None


class AutomationAssessment(BaseModel):
    candidate: bool
    reason: str
    hints: AutomationHints | None = None


class GeneratedTestCase(BaseModel):
    requirement_id: str
    feature: str | None = None
    description: str
    test_objective: str
    priority: Literal["P0", "P1", "P2", "P3"]
    severity: Literal["critical", "major", "minor", "trivial"]
    preconditions: list[str]
    test_data: dict[str, str] = Field(default_factory=dict)
    steps: list[TestStep]
    expected_result: str
    post_conditions: list[str] = Field(default_factory=list)
    # Only true scenario categories -- regression/smoke are execution
    # classifications of a scenario, not scenarios themselves, and are
    # expressed as tags (@regression, @smoke, @sanity) instead.
    test_type: Literal["functional", "negative", "edge_case"]
    tags: list[str] = Field(default_factory=list)
    # 1-based positions into this same generation batch's test_cases list --
    # the LLM can't reference final test_ids because it doesn't know them
    # yet (they're assigned by the agent after generation, same as
    # requirement_id). Resolved to real TC-xxx ids in TestCaseGeneratorAgent.
    depends_on_index: list[int] = Field(default_factory=list)
    automation: AutomationAssessment
    risk: Literal["low", "medium", "high"]
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str


class GeneratedTestCases(BaseModel):
    test_cases: list[GeneratedTestCase]
    coverage_notes: str | None = None


class TestCase(BaseModel):
    test_id: str
    requirement_id: str
    requirement_description: str
    source_reference: str | None = None
    module: str
    feature: str | None = None
    description: str
    test_objective: str
    priority: Literal["P0", "P1", "P2", "P3"]
    severity: Literal["critical", "major", "minor", "trivial"]
    preconditions: list[str]
    test_data: dict[str, str] = Field(default_factory=dict)
    steps: list[TestStep]
    expected_result: str
    post_conditions: list[str] = Field(default_factory=list)
    test_type: Literal["functional", "negative", "edge_case"]
    tags: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    automation: AutomationAssessment
    risk: Literal["low", "medium", "high"]
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str


class TestCaseGeneratorOutput(BaseModel):
    run_id: str
    prompt_version: str
    requirements: list[Requirement]
    test_cases: list[TestCase]
    coverage_notes: str | None = None
    ambiguities: list[str] = Field(default_factory=list)
    gaps: list[RequirementGap] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
