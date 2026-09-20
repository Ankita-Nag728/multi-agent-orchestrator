"""
Checkpointing gives us rollback: the last code version that passed review +
tests for a given task is kept in memory (and, when the DB layer is wired in,
persisted to the `checkpoints` table) so that if every retry for a *new* run
of the same task fails, we can restore the last known-good version instead of
handing the user broken code.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class Checkpoint:
    task_key: str
    code: str
    tests: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CheckpointStore:
    """In-memory checkpoint store, keyed by a stable hash/identifier of the
    task description. Swap this for a DB-backed store by keeping the same
    interface (save / get / has)."""

    def __init__(self) -> None:
        self._store: Dict[str, Checkpoint] = {}

    @staticmethod
    def key_for(task_description: str) -> str:
        return task_description.strip().lower()

    def save(self, task_description: str, code: str, tests: str) -> Checkpoint:
        key = self.key_for(task_description)
        cp = Checkpoint(task_key=key, code=code, tests=tests)
        self._store[key] = cp
        return cp

    def get(self, task_description: str) -> Optional[Checkpoint]:
        return self._store.get(self.key_for(task_description))

    def has(self, task_description: str) -> bool:
        return self.key_for(task_description) in self._store
