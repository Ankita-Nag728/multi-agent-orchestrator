"""TesterAgent: asks "can we actually prove this works?" It generates
assert-based tests with the LLM, then hands code+tests to the CodeExecutor
to actually run them -- it does not just ask the model if the code looks
correct (that's the Reviewer)."""

from __future__ import annotations

from dataclasses import dataclass

from services.llm_service import LLMService, extract_code
from tester.executor import CodeExecutor, ExecutionResult
from orchestrator.states import TestStatus

SYSTEM_PROMPT = (
    "You write Python test cases using plain `assert` statements (no "
    "pytest/unittest framework needed). Given a task and a candidate "
    "solution, write 3-6 assert statements that exercise normal cases, edge "
    "cases, and at least one invalid-input case if relevant. Assume the "
    "candidate solution's code will be available in the same file above "
    "your asserts -- do NOT redefine the function, just write the asserts. "
    "Return ONLY a fenced python code block containing the assert "
    "statements, nothing else."
)


@dataclass
class TestOutcome:
    status: TestStatus
    tests_code: str
    execution: ExecutionResult


class TesterAgent:
    def __init__(self, llm: LLMService, executor: CodeExecutor) -> None:
        self.llm = llm
        self.executor = executor

    def generate_tests(self, task: str, code: str) -> str:
        prompt = f"Task:\n{task}\n\nCandidate solution:\n```python\n{code}\n```"
        response = self.llm.generate(prompt, system=SYSTEM_PROMPT, temperature=0.2)
        return extract_code(response.text)

    def test(self, task: str, code: str) -> TestOutcome:
        tests_code = self.generate_tests(task, code)
        execution = self.executor.run(code, tests_code)
        return TestOutcome(status=execution.status, tests_code=tests_code, execution=execution)
