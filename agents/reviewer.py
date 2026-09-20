"""ReviewerAgent: reads code (does not write it) and decides APPROVED /
REJECTED with feedback, purely by asking the LLM to judge correctness,
readability, and edge-case handling against the task description."""

from __future__ import annotations

from dataclasses import dataclass

from services.llm_service import LLMService, LLMServiceError
from orchestrator.states import ReviewStatus

SYSTEM_PROMPT = (
    "You are a strict code reviewer. Given a task and a candidate Python "
    "solution, decide if it correctly and robustly solves the task. "
    "Respond with ONLY a JSON object, no prose, no markdown fences, in "
    'exactly this shape: {"status": "APPROVED" or "REJECTED", "feedback": '
    '"short, specific, actionable feedback"}. If APPROVED, feedback can be '
    "an empty string."
)


@dataclass
class ReviewResult:
    status: ReviewStatus
    feedback: str


class ReviewerAgent:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    def review(self, task: str, code: str) -> ReviewResult:
        prompt = f"Task:\n{task}\n\nCandidate solution:\n```python\n{code}\n```"
        try:
            data = self.llm.generate_json(prompt, system=SYSTEM_PROMPT)
            status_raw = str(data.get("status", "")).strip().upper()
            status = ReviewStatus.APPROVED if status_raw == "APPROVED" else ReviewStatus.REJECTED
            feedback = str(data.get("feedback", "")).strip()
        except LLMServiceError:
            # Fail closed: if we can't parse a verdict, treat it as rejected
            # so the orchestrator retries rather than silently accepting.
            status = ReviewStatus.REJECTED
            feedback = "Reviewer could not produce a parseable verdict; retrying."
        return ReviewResult(status=status, feedback=feedback)
