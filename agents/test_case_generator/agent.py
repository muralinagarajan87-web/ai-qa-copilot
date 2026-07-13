from __future__ import annotations

from agents.base.base_agent import BaseAgent
from agents.base.schemas import ArtifactKind, ValidationResult, WorkflowContext
from agents.test_case_generator.schemas import (
    GeneratedTestCases,
    TestCase,
    TestCaseGeneratorInput,
    TestCaseGeneratorOutput,
)


class TestCaseGeneratorAgent(BaseAgent[TestCaseGeneratorInput, TestCaseGeneratorOutput]):
    name = "test_case_generator"
    output_kind = ArtifactKind.TEST_CASES

    def build_input(self, context: WorkflowContext) -> TestCaseGeneratorInput:
        prd_ref = context.previous_outputs[ArtifactKind.PRD]
        return TestCaseGeneratorInput(run_id=context.run_id, source_document=prd_ref)

    def _run(self, input: TestCaseGeneratorInput, context: WorkflowContext) -> TestCaseGeneratorOutput:
        prd_text = self.artifact_manager.load(input.source_document).decode("utf-8")
        prompt = self._build_prompt(prd_text, input.module_hint)
        temperature = self.config.get("temperature", 0.2)

        response = self.llm.generate(
            prompt, system=self.prompt, temperature=temperature, response_schema=GeneratedTestCases
        )
        generated = GeneratedTestCases.model_validate(response.parsed)

        test_cases = [
            TestCase(test_id=f"TC-{index + 1:03d}", **draft.model_dump())
            for index, draft in enumerate(generated.test_cases)
        ]
        return TestCaseGeneratorOutput(
            run_id=context.run_id, test_cases=test_cases, coverage_notes=generated.coverage_notes
        )

    def validate(self, output: TestCaseGeneratorOutput) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        seen_ids: set[str] = set()

        if not output.test_cases:
            errors.append("No test cases were generated")

        for test_case in output.test_cases:
            if test_case.test_id in seen_ids:
                errors.append(f"Duplicate test_id: {test_case.test_id}")
            seen_ids.add(test_case.test_id)
            if not test_case.steps:
                errors.append(f"{test_case.test_id}: no test steps")
            if not test_case.expected_result.strip():
                errors.append(f"{test_case.test_id}: missing expected result")
            if not test_case.preconditions:
                warnings.append(f"{test_case.test_id}: no preconditions specified")

        return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)

    def explain(self, output: TestCaseGeneratorOutput) -> str:
        by_priority: dict[str, int] = {}
        for test_case in output.test_cases:
            by_priority[test_case.priority] = by_priority.get(test_case.priority, 0) + 1
        automatable = sum(1 for test_case in output.test_cases if test_case.automation_candidate)

        priority_summary = ", ".join(f"{count} {priority}" for priority, count in sorted(by_priority.items()))
        parts = [
            f"Generated {len(output.test_cases)} test cases ({priority_summary})",
            f"{automatable} flagged as automation candidates",
        ]
        if output.coverage_notes:
            parts.append(f"Coverage notes: {output.coverage_notes}")
        return " | ".join(parts)

    def _build_prompt(self, prd_text: str, module_hint: str | None) -> str:
        sections = [f"# Source Document\n\n{prd_text}"]
        if module_hint:
            sections.append(f"# Module Hint\n\n{module_hint}")
        return "\n\n".join(sections)
