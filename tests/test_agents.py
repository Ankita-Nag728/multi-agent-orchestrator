from unittest.mock import MagicMock

from agents.coder import CoderAgent
from agents.reviewer import ReviewerAgent
from agents.consensus import ConsensusEngine
from orchestrator.states import ReviewStatus, TestStatus, ConsensusResult
from services.llm_service import LLMResponse


def test_coder_extracts_fenced_code():
    llm = MagicMock()
    llm.generate.return_value = LLMResponse(
        text="Here you go:\n```python\ndef factorial(n):\n    return 1\n```", raw={}
    )
    coder = CoderAgent(llm)
    code = coder.generate_code("factorial")
    assert code == "def factorial(n):\n    return 1"


def test_coder_includes_feedback_in_prompt():
    llm = MagicMock()
    llm.generate.return_value = LLMResponse(text="```python\npass\n```", raw={})
    coder = CoderAgent(llm)
    coder.generate_code("task", feedback="handle negatives", previous_code="def f(): pass")
    prompt = llm.generate.call_args.args[0]
    assert "handle negatives" in prompt
    assert "def f(): pass" in prompt


def test_reviewer_parses_approved():
    llm = MagicMock()
    llm.generate_json.return_value = {"status": "APPROVED", "feedback": ""}
    reviewer = ReviewerAgent(llm)
    result = reviewer.review("task", "code")
    assert result.status == ReviewStatus.APPROVED


def test_reviewer_parses_rejected_with_feedback():
    llm = MagicMock()
    llm.generate_json.return_value = {"status": "REJECTED", "feedback": "no negative handling"}
    reviewer = ReviewerAgent(llm)
    result = reviewer.review("task", "code")
    assert result.status == ReviewStatus.REJECTED
    assert "negative" in result.feedback


def test_consensus_accept():
    engine = ConsensusEngine()
    assert engine.decide(ReviewStatus.APPROVED, TestStatus.PASS) == ConsensusResult.ACCEPT


def test_consensus_retry():
    engine = ConsensusEngine()
    assert engine.decide(ReviewStatus.REJECTED, TestStatus.FAIL) == ConsensusResult.RETRY


def test_consensus_disagree():
    engine = ConsensusEngine()
    assert engine.decide(ReviewStatus.APPROVED, TestStatus.FAIL) == ConsensusResult.DISAGREE
    assert engine.decide(ReviewStatus.REJECTED, TestStatus.PASS) == ConsensusResult.DISAGREE
