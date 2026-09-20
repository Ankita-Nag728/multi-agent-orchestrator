from unittest.mock import MagicMock, patch

from orchestrator.orchestrator import Orchestrator
from orchestrator.states import State


def _mock_llm_accept_first_try():
    llm = MagicMock()
    llm.generate.side_effect = [
        MagicMock(text="```python\ndef f():\n    return 1\n```"),  # coder
        MagicMock(text="```python\nassert f() == 1\n```"),  # tester (test gen)
    ]
    llm.generate_json.return_value = {"status": "APPROVED", "feedback": ""}
    return llm


def test_accepts_on_first_success():
    llm = _mock_llm_accept_first_try()
    orch = Orchestrator(llm=llm, max_attempts=3)
    result = orch.run_task("return 1")
    assert result.final_state == State.DONE
    assert result.accepted is True
    assert result.attempts_used == 1


def test_retries_then_rolls_back_when_exhausted():
    llm = MagicMock()
    # Every coder call returns broken code; reviewer always rejects.
    llm.generate.side_effect = [
        MagicMock(text="```python\ndef f(): return 1/0\n```"),
        MagicMock(text="```python\nassert f() == 1\n```"),
        MagicMock(text="```python\ndef f(): return 1/0\n```"),
        MagicMock(text="```python\nassert f() == 1\n```"),
    ]
    llm.generate_json.return_value = {"status": "REJECTED", "feedback": "division by zero"}

    orch = Orchestrator(llm=llm, max_attempts=2)
    with patch("time.sleep"):  # skip real backoff delay in tests
        result = orch.run_task("broken task")

    assert result.final_state == State.FAILED
    assert result.accepted is False
    assert result.attempts_used == 2


def test_checkpoint_enables_rollback_on_second_run():
    llm_good = _mock_llm_accept_first_try()
    orch = Orchestrator(llm=llm_good, max_attempts=1)
    first = orch.run_task("return 1")
    assert first.accepted

    # Second run for the SAME task fails every attempt, but a checkpoint
    # exists from the first run, so we should roll back instead of failing.
    llm_bad = MagicMock()
    llm_bad.generate.side_effect = [
        MagicMock(text="```python\ndef f(): return 2\n```"),
        MagicMock(text="```python\nassert f() == 1\n```"),
    ]
    llm_bad.generate_json.return_value = {"status": "REJECTED", "feedback": "wrong value"}
    orch.llm = llm_bad
    orch.coder.llm = llm_bad
    orch.reviewer.llm = llm_bad
    orch.tester.llm = llm_bad

    with patch("time.sleep"):
        second = orch.run_task("return 1")

    assert second.final_state == State.ROLLBACK
    assert second.rolled_back is True
    assert second.code == "def f():\n    return 1"
