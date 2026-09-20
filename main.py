"""Run a single task through the orchestrator from the command line, with no
FastAPI/React/Postgres involved. Useful for quickly sanity-checking the
agent pipeline against your local Ollama install.

Usage:
    python main.py "Create a Python function that checks whether a number is prime"
"""

from __future__ import annotations

import sys

from orchestrator.orchestrator import Orchestrator
from services.llm_service import LLMService


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: python main.py "<task description>"')
        return 1

    task = " ".join(sys.argv[1:])
    llm = LLMService()

    if not llm.is_reachable():
        print(
            f"⚠️  Could not reach Ollama at {llm.base_url}. "
            f"Make sure `ollama serve` is running and you've pulled {llm.model}."
        )
        return 1

    orchestrator = Orchestrator(llm=llm, on_event=lambda e: print(f"[{e.state.value}] {e.message}"))
    result = orchestrator.run_task(task)

    print("\n" + "=" * 60)
    print(f"Final state : {result.final_state.value}")
    print(f"Accepted    : {result.accepted}")
    print(f"Rolled back : {result.rolled_back}")
    print(f"Attempts    : {result.attempts_used}")
    print("=" * 60)
    if result.code:
        print("\nFinal code:\n")
        print(result.code)
    if result.tests:
        print("\nTests:\n")
        print(result.tests)

    return 0 if result.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
