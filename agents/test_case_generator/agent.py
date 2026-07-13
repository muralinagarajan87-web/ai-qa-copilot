from __future__ import annotations

from agents.base.base_agent import BaseAgent
from agents.base.schemas import ArtifactKind, ValidationResult, WorkflowContext
from agents.test_case_generator.schemas import (
    ExtractedRequirements,
    GeneratedTestCase,
    GeneratedTestCases,
    Requirement,
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
        temperature = self.config.get("temperature", 0.2)
        requirements_prompt = self._load_prompt_file(self.config.get("requirements_prompt", "requirements_v1.md"))

        requirements = self._extract_requirements(prd_text, input.module_hint, requirements_prompt, temperature, context)
        test_cases, coverage_notes = self._generate_test_cases(requirements, temperature, context)

        output = TestCaseGeneratorOutput(
            run_id=context.run_id,
            prompt_version=self.prompt_version,
            requirements=requirements,
            test_cases=test_cases,
            coverage_notes=coverage_notes,
        )
        self._write_human_report(context.run_id, output)
        return output

    def _extract_requirements(
        self, prd_text: str, module_hint: str | None, requirements_prompt: str, temperature: float, context: WorkflowContext
    ) -> list[Requirement]:
        prompt = self._build_extraction_prompt(prd_text, module_hint)
        response = self.llm.generate(
            prompt, system=requirements_prompt, temperature=temperature, response_schema=ExtractedRequirements
        )
        self._record_llm_call(response, context=context, temperature=temperature, purpose="extract_requirements")

        extracted = ExtractedRequirements.model_validate(response.parsed)
        if not extracted.requirements:
            raise RuntimeError("No requirements could be extracted from the source document")

        return [
            Requirement(requirement_id=f"REQ-{index + 1:03d}", **draft.model_dump())
            for index, draft in enumerate(extracted.requirements)
        ]

    def _generate_test_cases(
        self, requirements: list[Requirement], temperature: float, context: WorkflowContext
    ) -> tuple[list[TestCase], str | None]:
        prompt = self._build_generation_prompt(requirements)
        response = self.llm.generate(
            prompt, system=self.prompt, temperature=temperature, response_schema=GeneratedTestCases
        )
        self._record_llm_call(response, context=context, temperature=temperature, purpose="generate_test_cases")

        generated = GeneratedTestCases.model_validate(response.parsed)
        requirements_by_id = {requirement.requirement_id: requirement for requirement in requirements}

        # test_id assignment is purely positional, so the full position -> id
        # map can be built upfront and used both for each test case's own id
        # and for resolving depends_on_index -> depends_on below.
        test_ids_by_position = {index + 1: f"TC-{index + 1:03d}" for index in range(len(generated.test_cases))}

        test_cases: list[TestCase] = []
        for index, draft in enumerate(generated.test_cases):
            requirement = requirements_by_id.get(draft.requirement_id)
            if requirement is None:
                raise RuntimeError(
                    f"Generated test case referenced unknown requirement_id '{draft.requirement_id}' "
                    f"(known: {sorted(requirements_by_id)})"
                )
            test_id = test_ids_by_position[index + 1]
            depends_on = self._resolve_dependencies(index + 1, draft, test_ids_by_position)

            test_cases.append(
                TestCase(
                    test_id=test_id,
                    requirement_id=draft.requirement_id,
                    requirement_description=requirement.description,
                    source_reference=requirement.source_reference,
                    module=requirement.module,
                    feature=draft.feature,
                    description=draft.description,
                    test_objective=draft.test_objective,
                    priority=draft.priority,
                    severity=draft.severity,
                    preconditions=draft.preconditions,
                    test_data=draft.test_data,
                    steps=draft.steps,
                    expected_result=draft.expected_result,
                    test_type=draft.test_type,
                    tags=draft.tags,
                    depends_on=depends_on,
                    automation=draft.automation,
                    risk=draft.risk,
                    confidence=draft.confidence,
                    confidence_reason=draft.confidence_reason,
                )
            )
        return test_cases, generated.coverage_notes

    def _resolve_dependencies(
        self, own_position: int, draft: GeneratedTestCase, test_ids_by_position: dict[int, str]
    ) -> list[str]:
        resolved: list[str] = []
        for position in draft.depends_on_index:
            if position == own_position:
                continue
            target_id = test_ids_by_position.get(position)
            if target_id is not None and target_id not in resolved:
                resolved.append(target_id)
        return resolved

    def validate(self, output: TestCaseGeneratorOutput) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        known_requirement_ids = {requirement.requirement_id for requirement in output.requirements}
        seen_test_ids: set[str] = set()
        covered_requirement_ids: set[str] = set()

        if not output.requirements:
            errors.append("No requirements were extracted")
        if not output.test_cases:
            errors.append("No test cases were generated")

        known_test_ids = {test_case.test_id for test_case in output.test_cases}
        for test_case in output.test_cases:
            if test_case.test_id in seen_test_ids:
                errors.append(f"Duplicate test_id: {test_case.test_id}")
            seen_test_ids.add(test_case.test_id)

            if test_case.requirement_id not in known_requirement_ids:
                errors.append(f"{test_case.test_id}: references unknown requirement_id '{test_case.requirement_id}'")
            covered_requirement_ids.add(test_case.requirement_id)

            if not test_case.steps:
                errors.append(f"{test_case.test_id}: no test steps")
            if not test_case.expected_result.strip():
                errors.append(f"{test_case.test_id}: missing expected result")
            if not test_case.preconditions:
                warnings.append(f"{test_case.test_id}: no preconditions specified")
            for dependency_id in test_case.depends_on:
                if dependency_id not in known_test_ids:
                    errors.append(f"{test_case.test_id}: depends_on references unknown test_id '{dependency_id}'")
            if test_case.automation.candidate and test_case.automation.hints is None:
                warnings.append(f"{test_case.test_id}: flagged as automation candidate but has no automation hints")

        for requirement_id in sorted(known_requirement_ids - covered_requirement_ids):
            warnings.append(f"{requirement_id}: no test case references this requirement")

        return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)

    def explain(self, output: TestCaseGeneratorOutput) -> str:
        by_priority: dict[str, int] = {}
        for test_case in output.test_cases:
            by_priority[test_case.priority] = by_priority.get(test_case.priority, 0) + 1
        automatable = sum(1 for test_case in output.test_cases if test_case.automation.candidate)

        priority_summary = ", ".join(f"{count} {priority}" for priority, count in sorted(by_priority.items()))
        parts = [
            f"Extracted {len(output.requirements)} requirements",
            f"generated {len(output.test_cases)} test cases ({priority_summary})",
            f"{automatable} flagged as automation candidates",
        ]
        if output.coverage_notes:
            parts.append(f"Coverage notes: {output.coverage_notes}")
        return " | ".join(parts)

    def _build_extraction_prompt(self, prd_text: str, module_hint: str | None) -> str:
        sections = [f"# Source Document\n\n{prd_text}"]
        if module_hint:
            sections.append(f"# Module Hint\n\n{module_hint}")
        return "\n\n".join(sections)

    def _build_generation_prompt(self, requirements: list[Requirement]) -> str:
        lines = ["# Requirements", ""]
        for requirement in requirements:
            lines.append(
                f"- requirement_id: {requirement.requirement_id}\n"
                f"  module: {requirement.module}\n"
                f"  description: {requirement.description}"
            )
        return "\n".join(lines)

    def _write_human_report(self, run_id: str, output: TestCaseGeneratorOutput) -> None:
        markdown = self._render_markdown(output)
        path = f"artifacts/runs/{run_id}/test_cases/Manual_TestCases.md"
        self.artifact_manager.file_service.write(path, markdown, run_id)

    def _render_markdown(self, output: TestCaseGeneratorOutput) -> str:
        """Human-readable QA document. Automation hints (locators/actions/
        assertions/complexity) are deliberately excluded here -- they are
        machine-facing detail for the Automation Agent, not something a
        manual QA reviewer needs to read through.
        """
        lines: list[str] = [
            "# Manual Test Cases",
            "",
            f"Run ID: `{output.run_id}` | Prompt version: `{output.prompt_version}` | "
            f"{len(output.test_cases)} test cases across {len(output.requirements)} requirements",
            "",
        ]
        if output.coverage_notes:
            lines += [f"**Coverage notes:** {output.coverage_notes}", ""]

        lines += [
            "## Summary",
            "",
            "| Req ID | Test Case ID | Description | Module | Priority | Automation Candidate |",
            "|---|---|---|---|---|---|",
        ]
        for test_case in output.test_cases:
            automation_flag = "Yes" if test_case.automation.candidate else "No"
            lines.append(
                f"| {test_case.requirement_id} | {test_case.test_id} | {test_case.description} | "
                f"{test_case.module} | {test_case.priority} | {automation_flag} |"
            )

        lines += ["", "## Test Case Detail", ""]
        for test_case in output.test_cases:
            module_line = test_case.module if not test_case.feature else f"{test_case.module} / {test_case.feature}"
            precondition_lines = [f"- {item}" for item in test_case.preconditions] or ["- None"]
            automation_flag = "Yes" if test_case.automation.candidate else "No"
            tags_line = " ".join(f"`@{tag}`" for tag in test_case.tags) or "None"
            depends_line = ", ".join(test_case.depends_on) or "None"

            lines += [f"### {test_case.test_id} -- {test_case.description}", ""]
            lines += [f"**Requirement ID**  \n{test_case.requirement_id}", ""]
            lines += [f"**Requirement Description**  \n{test_case.requirement_description}", ""]
            if test_case.source_reference:
                lines += [f"**Source Reference**  \n{test_case.source_reference}", ""]
            lines += [f"**Module / Feature**  \n{module_line}", ""]
            lines += [f"**Test Objective**  \n{test_case.test_objective}", ""]
            lines += ["**Preconditions**", *precondition_lines, ""]

            lines += ["**Test Data**", ""]
            if test_case.test_data:
                lines += ["| Field | Value |", "|---|---|"]
                lines += [f"| {key} | {value} |" for key, value in test_case.test_data.items()]
            else:
                lines += ["None"]
            lines += [""]

            lines += ["**Test Steps**", "", "| Step | Action | Expected Result |", "|---|---|---|"]
            lines += [
                f"| {step_index + 1} | {step.action} | {step.expected} |"
                for step_index, step in enumerate(test_case.steps)
            ]
            lines += [""]

            lines += [f"**Expected Result (Overall)**  \n{test_case.expected_result}", ""]
            lines += [
                f"**Priority:** {test_case.priority} &nbsp;|&nbsp; **Severity:** {test_case.severity} "
                f"&nbsp;|&nbsp; **Risk:** {test_case.risk} &nbsp;|&nbsp; **Confidence:** {test_case.confidence} "
                f"({test_case.confidence_reason})",
                "",
            ]
            lines += [f"**Tags:** {tags_line}", ""]
            lines += [f"**Depends On:** {depends_line}", ""]
            lines += [
                f"**Automation Candidate:** {automation_flag} -- {test_case.automation.reason}",
                "",
                "---",
                "",
            ]

        return "\n".join(lines)
