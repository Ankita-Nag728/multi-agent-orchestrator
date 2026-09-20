from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    runs: Mapped[list["Run"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    status: Mapped[str] = mapped_column(String, default="PENDING")  # mirrors orchestrator.states.State
    final_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_tests: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts_used: Mapped[int] = mapped_column(Integer, default=0)
    rolled_back: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["Task"] = relationship(back_populates="runs")
    events: Mapped[list["AgentExecution"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AgentExecution.timestamp"
    )


class AgentExecution(Base):
    """One row per Orchestrator Event: a state transition / agent action
    with whatever structured data it produced (code, feedback, test output,
    etc.), used to render the frontend's execution timeline."""

    __tablename__ = "agent_executions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    state: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped["Run"] = relationship(back_populates="events")


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    task_key: Mapped[str] = mapped_column(String, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    code: Mapped[str] = mapped_column(Text)
    tests: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
