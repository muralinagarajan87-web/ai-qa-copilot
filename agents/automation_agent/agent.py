from __future__ import annotations

import json
import re
import subprocess

from agents.base.base_agent import BaseAgent
from agents.base.schemas import ArtifactKind, ReviewComment, ValidationResult, WorkflowContext
from agents.automation_agent.schemas import (
    AutomationAgentInput,
    AutomationAgentOutput,
    GeneratedFile,
    ModuleGeneration,
    SkippedTestCase,
    ToolCheckResult,
)
from agents.test_case_generator.schemas import TestCase, TestCaseGeneratorOutput

_FORBIDDEN_SUBSTRINGS = {
    "waitfortimeout(": "contains a forbidden waitForTimeout() hard wait",
    "xpath=": "contains a forbidden XPath locator",
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "module"


def _rewrap_quoted_literal(text: str) -> str:
    if '"' not in text:
        return f'"{text}"'
    return "'" + text.replace("\\'", "'").replace("'", "\\'") + "'"


def _fix_unescaped_quotes_in_test_titles(content: str) -> str:
    """`test_case.description` frequently quotes real UI text (e.g. "...shows
    the error message 'Epic sadface: ...'"), and the model is unreliable
    about escaping that when it interpolates the description into a
    single-quoted `test(...)`/`test.step(...)` title -- observed reproducing
    at the same line across repeated regenerations, so this is a stable
    model failure mode, not one-off noise. Deterministically rewrap those
    two known call sites (title ends right before `', {` or `', async`)
    instead of continuing to re-prompt for it.
    """
    content = re.sub(
        r"test\('(.*?)',(\s*\{)",
        lambda m: f"test({_rewrap_quoted_literal(m.group(1))},{m.group(2)}",
        content,
    )
    content = re.sub(
        r"test\.step\('(.*?)',(\s*async)",
        lambda m: f"test.step({_rewrap_quoted_literal(m.group(1))},{m.group(2)}",
        content,
    )
    return content


def _strip_unused_expect_import(content: str) -> str:
    """The prompt asks the model to only import `expect` when it's actually
    called in that file, but this is exactly the kind of small mechanical
    detail LLMs are inconsistent about -- observed failing on real runs.
    Enforce it deterministically instead of re-prompting: if `expect(` never
    appears outside the import itself, drop it from the import.
    """
    if re.search(r"\bexpect\(", content):
        return content

    def _drop_expect(match: re.Match) -> str:
        names = [n.strip() for n in match.group(1).split(",") if n.strip() and n.strip() != "expect"]
        return "{ " + ", ".join(names) + " }"

    return re.sub(
        r"\{\s*([^}]*\bexpect\b[^}]*)\s*\}(?=\s*from\s*['\"]@playwright/test['\"])",
        _drop_expect,
        content,
        count=1,
    )


def _extract_application_under_test_section(prd_text: str) -> str:
    """The PRD's Requirements/Out of Scope sections restate what's already
    in each rendered test case -- only the Application Under Test section
    (real URLs, selectors, accepted test data) adds anything the Automation
    Agent needs. Embedding the whole PRD per module call was pushing
    Login's prompt over Groq's per-request TPM ceiling for no benefit.
    Falls back to the full text if the expected heading isn't found, so an
    unexpected PRD shape degrades gracefully instead of losing grounding.
    """
    match = re.search(
        r"^##\s*Application Under Test\s*$(.*?)(?=^##\s|\Z)", prd_text, flags=re.MULTILINE | re.DOTALL
    )
    if not match:
        return prd_text
    return "## Application Under Test\n" + match.group(1).strip()


class AutomationAgent(BaseAgent[AutomationAgentInput, AutomationAgentOutput]):
    name = "automation"
    output_kind = ArtifactKind.PLAYWRIGHT_CODE

    def build_input(self, context: WorkflowContext) -> AutomationAgentInput:
        test_cases_ref = context.previous_outputs[ArtifactKind.TEST_CASES]
        data = json.loads(self.artifact_manager.load(test_cases_ref))
        test_case_output = TestCaseGeneratorOutput.model_validate(data)

        source_document_text = None
        prd_ref = context.previous_outputs.get(ArtifactKind.PRD)
        if prd_ref is not None:
            full_prd_text = self.artifact_manager.load(prd_ref).decode("utf-8")
            source_document_text = _extract_application_under_test_section(full_prd_text)

        return AutomationAgentInput(
            run_id=context.run_id,
            test_cases=test_case_output.test_cases,
            review_comments=context.review_comments,
            source_document_text=source_document_text,
        )

    def _run(self, input: AutomationAgentInput, context: WorkflowContext) -> AutomationAgentOutput:
        candidates = [test_case for test_case in input.test_cases if test_case.automation.candidate]
        skipped = [test_case for test_case in input.test_cases if not test_case.automation.candidate]

        if not candidates:
            raise RuntimeError("No automation-candidate test cases to generate code for")

        temperature = self.config.get("temperature", 0.2)
        groups = self._group_by_module(candidates)

        files: list[GeneratedFile] = []
        coverage: dict[str, list[str]] = {}

        for module, module_test_cases in groups.items():
            prompt = self._build_module_prompt(
                module, module_test_cases, input.review_comments, input.source_document_text
            )
            response = self.llm.generate(
                prompt, system=self.prompt, temperature=temperature, response_schema=ModuleGeneration
            )
            self._record_llm_call(
                response, context=context, temperature=temperature, purpose=f"generate_module:{_slugify(module)}"
            )
            result = ModuleGeneration.model_validate(response.parsed)

            page_object_path = f"pages/{result.page_object_class_name}.ts"
            spec_path = f"tests/{_slugify(module)}.spec.ts"

            page_object_content = _strip_unused_expect_import(result.page_object_content)
            spec_content = _fix_unescaped_quotes_in_test_titles(result.spec_content)
            spec_content = _strip_unused_expect_import(spec_content)

            files.append(GeneratedFile(path=page_object_path, content=page_object_content, file_type="page_object"))
            files.append(GeneratedFile(path=spec_path, content=spec_content, file_type="test"))

            for test_case in module_test_cases:
                coverage[test_case.test_id] = [page_object_path, spec_path]

        for generated_file in files:
            self.artifact_manager.file_service.write(
                f"playwright/{generated_file.path}", generated_file.content, context.run_id
            )

        lint_result = self._run_tool(["npx", "eslint", "."], "eslint")
        typecheck_result = self._run_tool(["npx", "tsc", "--noEmit"], "tsc")

        return AutomationAgentOutput(
            run_id=context.run_id,
            prompt_version=self.prompt_version,
            files=files,
            test_case_coverage=coverage,
            skipped_test_cases=[
                SkippedTestCase(test_id=test_case.test_id, reason=test_case.automation.reason) for test_case in skipped
            ],
            lint_result=lint_result,
            typecheck_result=typecheck_result,
        )

    def _group_by_module(self, test_cases: list[TestCase]) -> dict[str, list[TestCase]]:
        groups: dict[str, list[TestCase]] = {}
        for test_case in test_cases:
            groups.setdefault(test_case.module, []).append(test_case)
        return groups

    def _build_module_prompt(
        self,
        module: str,
        test_cases: list[TestCase],
        review_comments: list[ReviewComment],
        source_document_text: str | None,
    ) -> str:
        include_hints = source_document_text is None
        lines = [f"# Module: {module}", "", "# Test Cases", ""]
        for test_case in test_cases:
            lines.append(self._render_test_case(test_case, include_hints=include_hints))
        if source_document_text:
            lines.append(
                "# Source Document (use for REAL element identifiers if it names any -- "
                "see 'Grounded Locators' in your instructions)"
            )
            lines.append(source_document_text)
            lines.append("")
        if review_comments:
            lines.append("# Review Feedback To Fix")
            for comment in review_comments:
                suggestion = f" Suggested fix: {comment.suggested_fix}" if comment.suggested_fix else ""
                lines.append(f"- [{comment.severity}] {comment.file}: {comment.message}{suggestion}")
        return "\n".join(lines)

    def _render_test_case(self, test_case: TestCase, include_hints: bool = True) -> str:
        hints = test_case.automation.hints if include_hints else None
        lines = [
            # test_objective and test_type are omitted here: they're not
            # used to drive codegen (description + steps + test_data
            # already say what to do; tags carry the smoke/regression
            # bucketing) and they measurably push the largest modules over
            # Groq's per-request token ceiling.
            f"## {test_case.test_id}: {test_case.description}",
            f"- tags: {test_case.tags}",
            f"- preconditions: {test_case.preconditions}",
            f"- test_data: {test_case.test_data}",
            "- steps:",
        ]
        for index, step in enumerate(test_case.steps, start=1):
            lines.append(f"  {index}. {step.action} -> expected: {step.expected}")
        lines.append(f"- expected_result: {test_case.expected_result}")
        if test_case.post_conditions:
            lines.append(f"- post_conditions: {test_case.post_conditions}")
        if test_case.depends_on:
            lines.append(f"- depends_on: {test_case.depends_on}")
        if hints:
            lines.append(f"- suggested page_object: {hints.page_object}")
            lines.append(f"- suggested locators: {hints.locators}")
            lines.append(f"- suggested actions: {hints.actions}")
            lines.append(f"- suggested assertions: {hints.assertions}")
        lines.append("")
        return "\n".join(lines)

    def _run_tool(self, command: list[str], tool_name: str) -> ToolCheckResult:
        playwright_root = self.artifact_manager.file_service.root / "playwright"
        try:
            result = subprocess.run(command, cwd=playwright_root, capture_output=True, text=True, timeout=120)
        except (subprocess.TimeoutExpired, FileNotFoundError) as error:
            return ToolCheckResult(tool=tool_name, passed=False, output=f"Failed to run {tool_name}: {error}")
        output = (result.stdout + result.stderr).strip()
        return ToolCheckResult(tool=tool_name, passed=result.returncode == 0, output=output[-4000:])

    def validate(self, output: AutomationAgentOutput) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if not output.files:
            errors.append("No files were generated")

        for generated_file in output.files:
            content_lower = generated_file.content.lower()
            for pattern, message in _FORBIDDEN_SUBSTRINGS.items():
                if pattern in content_lower:
                    errors.append(f"{generated_file.path}: {message}")

        # Assertions may live directly in a spec file, or be delegated to
        # Page Object helper methods (e.g. `expectPageTitleEquals()` that
        # internally calls `expect()`) -- a legitimate, common POM pattern
        # that keeps specs readable. So a spec file is only flagged if
        # NEITHER it nor any non-test file in this output contains a real
        # assertion -- checking the spec file in isolation would reject
        # exactly the pattern our own prompt asks for.
        non_test_content = "\n".join(f.content for f in output.files if f.file_type != "test")
        for generated_file in output.files:
            if generated_file.file_type != "test":
                continue
            if "expect(" not in generated_file.content and "expect(" not in non_test_content:
                errors.append(f"{generated_file.path}: no expect() assertions found in the spec file or any page object")

        if output.lint_result and not output.lint_result.passed:
            warnings.append(f"eslint reported issues -- see lint_result.output for detail")
        if output.typecheck_result and not output.typecheck_result.passed:
            warnings.append(f"tsc reported issues -- see typecheck_result.output for detail")

        return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)

    def explain(self, output: AutomationAgentOutput) -> str:
        automated = len(output.test_case_coverage)
        parts = [
            f"Generated {len(output.files)} files covering {automated} test cases",
            f"{len(output.skipped_test_cases)} skipped (not automation candidates)",
        ]
        if output.lint_result:
            parts.append(f"eslint: {'passed' if output.lint_result.passed else 'FAILED'}")
        if output.typecheck_result:
            parts.append(f"tsc: {'passed' if output.typecheck_result.passed else 'FAILED'}")
        return " | ".join(parts)
