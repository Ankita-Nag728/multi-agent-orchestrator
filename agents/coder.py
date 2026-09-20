"""CoderAgent: turns a task description (plus optional reviewer feedback
from a previous attempt) into Python code. It never decides whether the code
is good -- that's the Reviewer's job."""

from __future__ import annotations

from typing import Optional

from services.llm_service import LLMService, extract_code

SYSTEM_PROMPT = (
    "You are a precise, senior Python engineer. You write a single, complete, "
    "self-contained Python function or small module that solves the given "
    "task. Return ONLY a fenced python code block, with no explanation "
    "before or after it. Include type hints and handle obvious edge cases "
    "(e.g. negative numbers, empty input) unless told otherwise."
)


class CoderAgent:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    def generate_code(self, task: str, feedback: Optional[str] = None, previous_code: Optional[str] = None) -> str:
        prompt = f"Task:\n{task}\n"
        if feedback:
            prompt += (
                f"\nYour previous attempt was rejected. Feedback:\n{feedback}\n"
            )
        if previous_code:
            prompt += f"\nPrevious attempt:\n```python\n{previous_code}\n```\n"
        prompt += "\nWrite the corrected/complete solution now."

        response = self.llm.generate(prompt, system=SYSTEM_PROMPT, temperature=0.2)
        return extract_code(response.text)
