"""ORM table definitions.

Six persisted entities cover the whole HaqFlow backend:
cases, situations, programs, documents, matches, and tasks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (
    CaseStatus,
    DocumentStatus,
    MatchLevel,
    TaskPriority,
    TaskStatus,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    """A single person's help-seeking session ("what happened to me")."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(
        String(20), default=CaseStatus.OPEN.value, nullable=False
    )
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    # The original free-form problem statement from the person.
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    situation: Mapped[Situation | None] = relationship(
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan",
    )
    matches: Mapped[list[Match]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[Task]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class Situation(Base):
    """Structured household/problem facts extracted by the AI intake agent.

    A few high-signal fields are typed columns for querying; the full extracted
    fact set lives in ``facts`` (JSON) and is what the rules engine reads.
    """

    __tablename__ = "situations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    household_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    province: Mapped[str | None] = mapped_column(String(60), nullable=True)
    employment_status: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Flexible bag of all structured facts the rules engine evaluates.
    facts: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    case: Mapped[Case] = relationship(back_populates="situation")


class Program(Base):
    """A verified support program and its published eligibility rules."""

    __tablename__ = "programs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)

    country: Mapped[str] = mapped_column(String(60), default="PK")
    region: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # List[Condition] — see app/rules/engine.py for the condition shape.
    eligibility_rules: Mapped[list] = mapped_column(JSON, default=list)
    # List[{name, description}] documents the person will need.
    required_documents: Mapped[list] = mapped_column(JSON, default=list)
    application_channel: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Trust & auditability (per the report's non-negotiables).
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )


class Match(Base):
    """A persisted eligibility result: one case evaluated against one program."""

    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )

    match_level: Mapped[str] = mapped_column(
        String(20), default=MatchLevel.NEEDS_INFO.value, nullable=False
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)

    matched_conditions: Mapped[list] = mapped_column(JSON, default=list)
    failed_conditions: Mapped[list] = mapped_column(JSON, default=list)
    missing_conditions: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    case: Mapped[Case] = relationship(back_populates="matches")
    program: Mapped[Program] = relationship()


class Document(Base):
    """A stored result from the Document Agent (Member 3 / AI side)."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )

    doc_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.RECEIVED.value, nullable=False
    )
    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    case: Mapped[Case] = relationship(back_populates="documents")


class Task(Base):
    """An action-plan item ("ActionItem") the person needs to complete."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[str | None] = mapped_column(
        ForeignKey("programs.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=TaskStatus.PENDING.value, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(20), default=TaskPriority.MEDIUM.value, nullable=False
    )
    due_date: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    case: Mapped[Case] = relationship(back_populates="tasks")
