from tester.executor import CodeExecutor
from orchestrator.states import TestStatus


def test_executor_pass():
    executor = CodeExecutor(timeout=5)
    code = "def add(a, b):\n    return a + b"
    tests = "assert add(2, 3) == 5"
    result = executor.run(code, tests)
    assert result.status == TestStatus.PASS


def test_executor_fail_on_assertion():
    executor = CodeExecutor(timeout=5)
    code = "def add(a, b):\n    return a - b"
    tests = "assert add(2, 3) == 5"
    result = executor.run(code, tests)
    assert result.status == TestStatus.FAIL


def test_executor_error_on_bad_code():
    executor = CodeExecutor(timeout=5)
    code = "def add(a, b)\n    return a + b"  # syntax error
    tests = "assert add(2, 3) == 5"
    result = executor.run(code, tests)
    assert result.status == TestStatus.ERROR


def test_executor_timeout():
    executor = CodeExecutor(timeout=1)
    code = "import time\ndef slow():\n    time.sleep(5)"
    tests = "slow()"
    result = executor.run(code, tests)
    assert result.status == TestStatus.TIMEOUT
