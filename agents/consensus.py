"""ConsensusEngine: combines the Reviewer's verdict and the Tester's result
into one decision. Deliberately a deterministic decision table, not another
LLM call -- that keeps the workflow predictable and auditable."""

from __future__ import annotations

from orchestrator.states import ReviewStatus, TestStatus, ConsensusResult


class ConsensusEngine:
    def decide(self, review_status: ReviewStatus, test_status: TestStatus) -> ConsensusResult:
        if review_status == ReviewStatus.APPROVED and test_status == TestStatus.PASS:
            return ConsensusResult.ACCEPT

        if review_status == ReviewStatus.REJECTED and test_status in (
            TestStatus.FAIL,
            TestStatus.ERROR,
            TestStatus.TIMEOUT,
        ):
            return ConsensusResult.RETRY

        # Agents disagree: reviewer liked it but tests failed, or vice versa.
        return ConsensusResult.DISAGREE
