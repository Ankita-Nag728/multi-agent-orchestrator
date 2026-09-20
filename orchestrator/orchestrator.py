"""
Orchestrator: the brain of the system. It is plain Python control flow, not
an AI model -- it decides which agent runs next, retries with exponential
backoff on rejection/failure, asks Consensus to adjudicate disagreement, and
rolls back to the last checkpoint if a task can't be solved within the
attempt budget.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

from agents.coder import CoderAgent
from agents.reviewer import ReviewerAgent
from agents.tester import TesterAgent
from agents.consensus import ConsensusEngine
from orchestrator.checkpoint import CheckpointStore
from orchestrator.states import State, ReviewStatus, TestStatus, ConsensusResult
from services.llm_service import LLMService
from tester.executor import CodeExecutor

MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))

EventCallback = Optional[Callable[["Event"], None]]


@dataclass
class Event:
    """One line of the execution trace. Human-readable + machine-readable."""

    state: State
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class RunResult:
    task: str
    final_state: State
    accepted: bool
    code: Optional[str]
    tests: Optional[str]
    attempts_used: int
    rolled_back: bool
    events: List[Event]


class Orchestrator:
    def __init__(
        self,
        llm: Optional[LLMService] = None,
        checkpoint_store: Optional[CheckpointStore] = None,
        max_attempts: int = MAX_ATTEMPTS,
        on_event: EventCallback = None,
    ) -> None:
        self.llm = llm or LLMService()
        self.coder = CoderAgent(self.llm)
        self.reviewer = ReviewerAgent(self.llm)
        self.executor = CodeExecutor()
        self.tester = TesterAgent(self.llm, self.executor)
        self.consensus = ConsensusEngine()
        self.checkpoints = checkpoint_store or CheckpointStore()
        self.max_attempts = max_attempts
        self.on_event = on_event

    def _emit(self, events: List[Event], state: State, message: str, **data) -> None:
        event = Event(state=state, message=message, data=data)
        events.append(event)
        if self.on_event:
            self.on_event(event)

    def run_task(self, task: str) -> RunResult:
        events: List[Event] = []
        self._emit(events, State.START, f"Run started for task: {task!r}")

        feedback: Optional[str] = None
        previous_code: Optional[str] = None
        attempt = 0

        while attempt < self.max_attempts:
            attempt += 1
            self._emit(events, State.CODING, f"Attempt {attempt}: generating code", attempt=attempt)

            code = self.coder.generate_code(task, feedback=feedback, previous_code=previous_code)
            self._emit(events, State.CODING, "Code generated", attempt=attempt, code=code)

            self._emit(events, State.REVIEWING, "Sending code to reviewer", attempt=attempt)
            review = self.reviewer.review(task, code)
            self._emit(
                events,
                State.REVIEWING,
                f"Reviewer verdict: {review.status.value}",
                attempt=attempt,
                status=review.status.value,
                feedback=review.feedback,
            )

            self._emit(events, State.TESTING, "Generating and running tests", attempt=attempt)
            outcome = self.tester.test(task, code)
            self._emit(
                events,
                State.TESTING,
                f"Test result: {outcome.status.value}",
                attempt=attempt,
                status=outcome.status.value,
                tests=outcome.tests_code,
                stdout=outcome.execution.stdout,
                stderr=outcome.execution.stderr,
            )

            decision = self.consensus.decide(review.status, outcome.status)
            self._emit(
                events,
                State.CONSENSUS,
                f"Consensus: {decision.value}",
                attempt=attempt,
                review=review.status.value,
                test=outcome.status.value,
            )

            if decision == ConsensusResult.ACCEPT:
                self.checkpoints.save(task, code, outcome.tests_code)
                self._emit(events, State.DONE, "Checkpoint saved; run accepted", attempt=attempt)
                return RunResult(
                    task=task,
                    final_state=State.DONE,
                    accepted=True,
                    code=code,
                    tests=outcome.tests_code,
                    attempts_used=attempt,
                    rolled_back=False,
                    events=events,
                )

            # RETRY or DISAGREE both loop back to coding, with feedback,
            # unless we're out of attempts.
            previous_code = code
            feedback = review.feedback or (
                f"Tests {outcome.status.value.lower()}. stderr: {outcome.execution.stderr[:500]}"
            )

            if attempt < self.max_attempts:
                backoff = 2 ** (attempt - 1)
                self._emit(
                    events,
                    State.RETRYING,
                    f"Backing off {backoff}s before retry {attempt + 1}",
                    attempt=attempt,
                    backoff_seconds=backoff,
                )
                time.sleep(backoff)

        # Attempts exhausted -- try to roll back to a previous good version.
        checkpoint = self.checkpoints.get(task)
        if checkpoint:
            self._emit(
                events,
                State.ROLLBACK,
                "Attempts exhausted; rolled back to last known-good checkpoint",
                checkpoint_created_at=checkpoint.created_at.isoformat(),
            )
            return RunResult(
                task=task,
                final_state=State.ROLLBACK,
                accepted=True,
                code=checkpoint.code,
                tests=checkpoint.tests,
                attempts_used=attempt,
                rolled_back=True,
                events=events,
            )

        self._emit(events, State.FAILED, "Attempts exhausted; no checkpoint to roll back to")
        return RunResult(
            task=task,
            final_state=State.FAILED,
            accepted=False,
            code=previous_code,
            tests=None,
            attempts_used=attempt,
            rolled_back=False,
            events=events,
        )
