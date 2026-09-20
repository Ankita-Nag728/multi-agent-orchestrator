from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RunCreateRequest(BaseModel):
    task: str = Field(..., min_length=1, description="Natural-language coding task")


class RunCreateResponse(BaseModel):
    run_id: str
    status: str


class EventOut(BaseModel):
    state: str
    message: str
    timestamp: datetime
    data: dict[str, Any] = {}

    class Config:
        from_attributes = True


class RunOut(BaseModel):
    run_id: str
    task: str
    status: str
    final_code: Optional[str] = None
    final_tests: Optional[str] = None
    attempts_used: int
    rolled_back: bool
    error: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    events: list[EventOut] = []


class RunSummaryOut(BaseModel):
    run_id: str
    task: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None


class HealthOut(BaseModel):
    ok: bool
    ollama_reachable: bool
    model: str
