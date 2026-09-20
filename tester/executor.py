"""
CodeExecutor actually runs generated code + generated tests, instead of
trusting the model's opinion of itself.

SECURITY NOTE: this runs AI-generated code with `subprocess.run()` in a
temporary directory on the host, with a wall-clock timeout. This is
convenient for a local MVP but is NOT a real sandbox: it does not restrict
filesystem or network access. See README.md for how to harden this with
Docker before pointing it at untrusted input.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from orchestrator.states import TestStatus

DEFAULT_TIMEOUT = int(os.getenv("EXECUTOR_TIMEOUT_SECONDS", "10"))


@dataclass
class ExecutionResult:
    status: TestStatus
    stdout: str
    stderr: str
    returncode: int | None


class CodeExecutor:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def run(self, code: str, tests_code: str) -> ExecutionResult:
        source = f"{code}\n\n# --- generated tests ---\n{tests_code}\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "candidate.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(source)

            try:
                proc = subprocess.run(
                    [sys.executable, script_path],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as e:
                return ExecutionResult(
                    status=TestStatus.TIMEOUT,
                    stdout=e.stdout or "",
                    stderr=f"Execution exceeded {self.timeout}s timeout.",
                    returncode=None,
                )
            except Exception as e:  # noqa: BLE001 - want any executor bug surfaced as ERROR, not a crash
                return ExecutionResult(status=TestStatus.ERROR, stdout="", stderr=str(e), returncode=None)

            if proc.returncode == 0:
                return ExecutionResult(TestStatus.PASS, proc.stdout, proc.stderr, proc.returncode)

            # AssertionError specifically means the tests ran and caught a
            # real bug (FAIL); anything else (SyntaxError, NameError, ...)
            # means the code/tests themselves are broken (ERROR).
            status = TestStatus.FAIL if "AssertionError" in proc.stderr else TestStatus.ERROR
            return ExecutionResult(status, proc.stdout, proc.stderr, proc.returncode)
