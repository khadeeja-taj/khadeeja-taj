"""Shared enums used by both models and schemas.

These string values are part of the shared team contract. Do NOT rename them
silently — Frontend (Member 4) and Follow-up (Member 5) depend on them.
"""

from enum import Enum


class CaseStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MatchLevel(str, Enum):
    """Outcome of the deterministic eligibility engine for one program.

    The engine NEVER claims official eligibility — only how well the person's
    structured facts line up with the program's published conditions.
    """

    ELIGIBLE = "eligible"            # every required condition matched
    LIKELY_ELIGIBLE = "likely"      # required matched, some optional unknown/failed
    NEEDS_INFO = "needs_info"       # a required condition is still unknown
    NOT_ELIGIBLE = "not_eligible"   # a required condition failed


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class DocumentStatus(str, Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"
