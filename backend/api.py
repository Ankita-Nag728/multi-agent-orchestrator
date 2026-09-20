"""
FastAPI backend: the bridge between the React frontend and the Orchestrator.
The frontend never talks to Ollama or the agents directly -- it POSTs a task
here, gets a run_id back immediately, and polls GET /runs/{run_id} for the
live execution timeline and final result.
"""

from __future__ import annotations

import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.database import SessionLocal, get_db, init_db
from backend import models, schemas
from orchestrator.orchestrator import Orchestrator, Event
from orchestrator.states import State
from services.llm_service import LLMService

os.makedirs("logs", exist_ok=True)
logging.basicConfig(level=logging.INFO, filename="logs/orchestrator.log")
logger = logging.getLogger("orchestrator-api")

app = FastAPI(title="Multi-Agent Orchestrator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    os.makedirs("logs", exist_ok=True)
    init_db()


def _execute_run(run_id: str, task_description: str) -> None:
    """Runs in a background thread. Owns its own DB session because the
    request-scoped session from the endpoint is closed by the time this
    runs."""
    db: Session = SessionLocal()
    try:
        run = db.get(models.Run, run_id)
        if run is None:
            return
        run.status = State.CODING.value
        db.commit()

        def on_event(event: Event) -> None:
            row = models.AgentExecution(
                run_id=run_id,
                state=event.state.value,
                message=event.message,
                data_json=json.dumps(_json_safe(event.data)),
                timestamp=event.timestamp,
            )
            db.add(row)
            run.status = event.state.value
            db.commit()
            logger.info("[%s] %s: %s", run_id, event.state.value, event.message)

        orchestrator = Orchestrator(llm=LLMService(), on_event=on_event)
        result = orchestrator.run_task(task_description)

        run.status = result.final_state.value
        run.final_code = result.code
        run.final_tests = result.tests
        run.attempts_used = result.attempts_used
        run.rolled_back = result.rolled_back
        run.finished_at = datetime.now(timezone.utc)
        if not result.accepted:
            run.error = "Task failed after exhausting all retry attempts with no checkpoint to roll back to."

        if result.accepted and result.code:
            db.add(
                models.Checkpoint(
                    task_key=task_description.strip().lower(),
                    run_id=run_id,
                    code=result.code,
                    tests=result.tests or "",
                )
            )
        db.commit()
    except Exception as e:  # noqa: BLE001 - surface any orchestrator crash on the run record
        db.rollback()
        run = db.get(models.Run, run_id)
        if run:
            run.status = State.FAILED.value
            run.error = str(e)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        logger.exception("Run %s crashed", run_id)
    finally:
        db.close()


def _json_safe(data: dict) -> dict:
    """Event.data can contain arbitrary strings (code, stderr, ...); this is
    just a defensive pass so json.dumps never blows up on odd types."""
    return {k: (v if isinstance(v, (str, int, float, bool, type(None))) else str(v)) for k, v in data.items()}


@app.get("/health", response_model=schemas.HealthOut)
def health() -> schemas.HealthOut:
    llm = LLMService()
    return schemas.HealthOut(ok=True, ollama_reachable=llm.is_reachable(), model=llm.model)


@app.post("/runs", response_model=schemas.RunCreateResponse, status_code=202)
def create_run(
    body: schemas.RunCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.RunCreateResponse:
    task = models.Task(description=body.task)
    db.add(task)
    db.flush()

    run = models.Run(task_id=task.id, status=State.START.value)
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_execute_run, run.id, body.task)

    return schemas.RunCreateResponse(run_id=run.id, status=run.status)


@app.get("/runs", response_model=list[schemas.RunSummaryOut])
def list_runs(limit: int = 20, db: Session = Depends(get_db)) -> list[schemas.RunSummaryOut]:
    runs = db.query(models.Run).order_by(models.Run.started_at.desc()).limit(limit).all()
    return [
        schemas.RunSummaryOut(
            run_id=r.id,
            task=r.task.description,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
        )
        for r in runs
    ]


@app.get("/runs/{run_id}", response_model=schemas.RunOut)
def get_run(run_id: str, db: Session = Depends(get_db)) -> schemas.RunOut:
    run = db.get(models.Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    events = [
        schemas.EventOut(
            state=e.state,
            message=e.message,
            timestamp=e.timestamp,
            data=json.loads(e.data_json) if e.data_json else {},
        )
        for e in run.events
    ]

    return schemas.RunOut(
        run_id=run.id,
        task=run.task.description,
        status=run.status,
        final_code=run.final_code,
        final_tests=run.final_tests,
        attempts_used=run.attempts_used,
        rolled_back=run.rolled_back,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
        events=events,
    )
