"""
The possible states of a Run. The Orchestrator is a deterministic state
machine over these values -- agents never choose the next state themselves,
they just report a result and the Orchestrator decides where to go.
"""

from enum import Enum


class State(str, Enum):
    START = "START"
    CODING = "CODING"
    REVIEWING = "REVIEWING"
    TESTING = "TESTING"
    CONSENSUS = "CONSENSUS"
    RETRYING = "RETRYING"
    ROLLBACK = "ROLLBACK"
    DONE = "DONE"
    FAILED = "FAILED"


class ReviewStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TestStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class ConsensusResult(str, Enum):
    ACCEPT = "ACCEPT"
    RETRY = "RETRY"
    DISAGREE = "DISAGREE"
