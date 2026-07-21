from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agents.base.schemas import ReviewComment
from agents.test_case_generator.schemas import TestCase


class AutomationAgentInput(BaseModel):
    run_id: str
    test_cases: list[TestCase]
    # Populated by the Orchestrator's WorkflowContext on the revision loop
    # (UNDER_REVIEW -> REVISION_NEEDED -> automation); empty on the first pass.
    review_comments: list[ReviewComment] = Field(default_factory=list)
    # The original PRD text, when it names real element identifiers (id,
    # data-test, etc. against a real application under test). When present,
    # the agent is instructed to use these exact identifiers instead of
    # inventing semantic locator names -- see agents/automation_agent/prompts/v1.md.
    # This is a stopgap for grounding locators in truth before the RAG/
    # pom_library milestone exists to look up real Page Objects properly.
    source_document_text: str | None = None


class GeneratedFile(BaseModel):
    path: str
    content: str
    file_type: Literal["test", "page_object", "fixture", "util"]


class SkippedTestCase(BaseModel):
    test_id: str
    reason: str


class ToolCheckResult(BaseModel):
    tool: str
    passed: bool
    output: str


class ModuleGeneration(BaseModel):
    """LLM-facing output for one module's worth of test cases -- one Page
    Object class plus one spec file implementing every automatable test
    case in that module. Kept as two raw TypeScript strings rather than a
    more structured AST-like schema; the file_service write + tsc/eslint
    verification step is what actually validates the code, not the schema.
    """

    page_object_class_name: str
    page_object_content: str
    spec_content: str


class AutomationAgentOutput(BaseModel):
    run_id: str
    prompt_version: str
    files: list[GeneratedFile]
    test_case_coverage: dict[str, list[str]] = Field(default_factory=dict)
    skipped_test_cases: list[SkippedTestCase] = Field(default_factory=list)
    lint_result: ToolCheckResult | None = None
    typecheck_result: ToolCheckResult | None = None
