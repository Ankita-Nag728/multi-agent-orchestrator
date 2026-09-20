# Multi-Agent AI Coding Orchestration Framework

A system where multiple specialized AI agents (Coder, Reviewer, Tester) collaborate
on a coding task under the control of a central **Orchestrator**: a deterministic
state machine that handles retries with exponential backoff, resolves agent
disagreement via a **Consensus** engine, executes generated tests in an isolated
subprocess, and rolls back to the last known-good **Checkpoint** on repeated failure.

```
USER → React → FastAPI → Orchestrator (state machine, retry, consensus, rollback)
                              │
                ┌─────────────┼─────────────┐
              CODER        REVIEWER       TESTER
                └─────────────┼─────────────┘
                          LLM Service
                              │
                        Ollama (Qwen2.5-Coder)
                              │
                        Code Executor → PASS/FAIL
                              │
                          Consensus
                         /          \
                     ACCEPT        RETRY → CODER
                        │
                    Checkpoint
                        │
                    PostgreSQL / SQLite
                        │
                     React UI
```

## Project layout

```
multi-agent-orchestrator/
├── agents/            # Coder, Reviewer, Tester, Consensus agents
├── orchestrator/       # State machine, retry/backoff, checkpointing
├── services/           # LLM service (Ollama abstraction)
├── tester/              # Sandboxed-ish code executor
├── backend/             # FastAPI app, SQLAlchemy models, schemas
├── frontend/            # React (Vite) dashboard
├── tests/                # Pytest unit tests (LLM calls mocked)
├── logs/                 # Execution trace logs written at runtime
└── main.py                # CLI entrypoint — run a task with no API/UI
```

## 1. Prerequisites

- Python 3.10+
- Node 18+ (for the frontend)
- [Ollama](https://ollama.com) installed and running locally
- A pulled coding model:
  ```bash
  ollama pull qwen2.5-coder:7b
  ```

## 2. Backend setup

```bash
cd multi-agent-orchestrator
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` if you want to override defaults (Ollama URL,
model name, database URL, retry limit).

### Run a single task from the CLI (no API/DB needed)

```bash
python main.py "Create a Python function that checks whether a number is prime"
```

This prints the full execution trace (coding → review → testing → consensus →
accept/retry/rollback) and the final code.

### Run the API + database

By default the app uses a local SQLite file (`orchestrator.db`) so there's
nothing to install. To use PostgreSQL instead, set:

```bash
export DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/orchestrator"
```

Then:

```bash
uvicorn backend.api:app --reload --port 8000
```

- `POST /runs` — start a new task, returns `{run_id}` immediately (runs in background)
- `GET /runs/{run_id}` — full trace: state, agent executions, attempts, final code
- `GET /runs` — list recent runs
- `GET /health` — liveness + whether Ollama is reachable

## 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open the printed localhost URL. Set `VITE_API_URL` (default
`http://localhost:8000`) if your API runs elsewhere.

## 4. Running tests

```bash
pytest
```

All LLM calls are mocked in the test suite — no Ollama needed to run tests.

## 5. Security note (read this before "production")

`tester/executor.py` runs AI-generated code with `subprocess.run()` on the host,
with a wall-clock timeout and a temp working directory. This is **not** a real
sandbox — a malicious or buggy generation could still touch the filesystem or
network within its process permissions. This MVP intentionally skips Docker
isolation to avoid disk pressure during development. Before running this
against untrusted input, isolate execution in a container with:

- no network access
- a read-only or ephemeral filesystem
- CPU/memory/time limits
- a non-root, low-privilege user

## 6. How a task flows through the system

1. `Orchestrator.run_task()` creates a `Run` in state `CODING`.
2. `CoderAgent` asks the LLM service to generate code for the task
   (with reviewer feedback appended on retries).
3. `ReviewerAgent` asks the LLM to approve/reject the code with feedback.
4. `TesterAgent` asks the LLM to generate `assert`-based tests, then
   `CodeExecutor` actually runs code + tests in a subprocess.
5. `ConsensusEngine` combines the (deterministic) review + test outcomes into
   `ACCEPT`, `RETRY`, or `DISAGREE`.
6. On `ACCEPT`, the code is saved as a `Checkpoint` and the run is `DONE`.
7. On `RETRY`/`DISAGREE`, the orchestrator waits `2**attempt` seconds
   (exponential backoff) and goes back to `CODING` with feedback, up to
   `MAX_ATTEMPTS` (default 3).
8. If attempts are exhausted, the orchestrator rolls back to the last
   successful `Checkpoint` for this task (if any) and marks the run `FAILED`
   otherwise.

## Resume blurb

> **Multi-Agent AI Coding Orchestration Framework** — Built a state-machine-based
> orchestration system coordinating specialized AI agents (coder, reviewer,
> tester) for code generation, review, automated test execution,
> consensus-based decision making, retry with exponential backoff, and
> checkpoint-based rollback. Integrated local LLM inference (Qwen2.5-Coder via
> Ollama) behind an abstraction layer, persisted full execution history to
> PostgreSQL/SQLite via SQLAlchemy, exposed it through a FastAPI backend, and
> visualized live run timelines in a React dashboard.
