"""
HaqFlow — Backend & Eligibility Engine (single-file edition)
============================================================
Member 2 deliverable: Python Backend / Database / Rules Engineer.

This is the WHOLE backend in one file so it is easy to share and run.
(A cleanly modularised version of the same code also lives in backend/app/.)

Quick start
-----------
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
    pip install -r requirements.txt
    uvicorn app:app --reload
    # open http://localhost:8000/docs

By default it uses a local SQLite file (haqflow.db) so there is ZERO setup.
To use the shared Supabase/Postgres team database instead, set an env var:
    export DATABASE_URL="postgresql+psycopg2://USER:PASS@HOST:5432/DBNAME"
    pip install psycopg2-binary

Core principle
--------------
The LLM may EXTRACT a person's facts, but this Python code DECIDES whether each
published condition is matched, failed, or still unknown. Eligibility
thresholds live in program DATA, never hard-coded in logic.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import Depends, FastAPI, Query, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    delete,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from starlette.exceptions import HTTPException as StarletteHTTPException

# --------------------------------------------------------------------------- #
# Database setup                                                               #
# --------------------------------------------------------------------------- #

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./haqflow.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Shared enums (part of the team contract — do not rename silently)            #
# --------------------------------------------------------------------------- #


class CaseStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MatchLevel(str, Enum):
    ELIGIBLE = "eligible"          # every required condition matched
    LIKELY_ELIGIBLE = "likely"     # required matched, some optional unknown/failed
    NEEDS_INFO = "needs_info"      # a required condition is still unknown
    NOT_ELIGIBLE = "not_eligible"  # a required condition failed


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


# --------------------------------------------------------------------------- #
# ORM models                                                                   #
# --------------------------------------------------------------------------- #


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(String(20), default=CaseStatus.OPEN.value)
    language: Mapped[str] = mapped_column(String(10), default="en")
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    situation: Mapped["Situation | None"] = relationship(
        back_populates="case", uselist=False, cascade="all, delete-orphan"
    )
    matches: Mapped[list["Match"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class Situation(Base):
    __tablename__ = "situations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), unique=True
    )
    household_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    province: Mapped[str | None] = mapped_column(String(60), nullable=True)
    employment_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    facts: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    case: Mapped[Case] = relationship(back_populates="situation")


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    country: Mapped[str] = mapped_column(String(60), default="PK")
    region: Mapped[str | None] = mapped_column(String(60), nullable=True)
    eligibility_rules: Mapped[list] = mapped_column(JSON, default=list)
    required_documents: Mapped[list] = mapped_column(JSON, default=list)
    application_channel: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"))
    match_level: Mapped[str] = mapped_column(String(20), default=MatchLevel.NEEDS_INFO.value)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    matched_conditions: Mapped[list] = mapped_column(JSON, default=list)
    failed_conditions: Mapped[list] = mapped_column(JSON, default=list)
    missing_conditions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    case: Mapped[Case] = relationship(back_populates="matches")
    program: Mapped[Program] = relationship()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    doc_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.RECEIVED.value)
    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    case: Mapped[Case] = relationship(back_populates="documents")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    program_id: Mapped[str | None] = mapped_column(
        ForeignKey("programs.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value)
    priority: Mapped[str] = mapped_column(String(20), default=TaskPriority.MEDIUM.value)
    due_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    case: Mapped[Case] = relationship(back_populates="tasks")


# --------------------------------------------------------------------------- #
# Pydantic schemas (the shared API contract)                                   #
# --------------------------------------------------------------------------- #


class SituationIn(BaseModel):
    household_size: int | None = Field(default=None, ge=0)
    monthly_income: float | None = Field(default=None, ge=0)
    province: str | None = None
    employment_status: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)


class SituationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    household_size: int | None
    monthly_income: float | None
    province: str | None
    employment_status: str | None
    facts: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CaseCreate(BaseModel):
    raw_text: str | None = None
    language: str = "en"
    summary: str | None = None
    situation: SituationIn | None = None


class CaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: CaseStatus
    language: str
    summary: str | None
    created_at: datetime
    updated_at: datetime


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    program_id: str
    match_level: MatchLevel
    score: float
    matched_conditions: list[dict[str, Any]]
    failed_conditions: list[dict[str, Any]]
    missing_conditions: list[dict[str, Any]]
    created_at: datetime


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    program_id: str | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: str | None
    created_at: datetime
    updated_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    doc_type: str | None
    filename: str | None
    status: DocumentStatus
    extracted_fields: dict[str, Any]
    confidence: float | None
    notes: str | None
    created_at: datetime


class CaseDetail(CaseSummary):
    raw_text: str | None
    situation: SituationOut | None = None
    matches: list[MatchOut] = Field(default_factory=list)
    tasks: list[TaskOut] = Field(default_factory=list)
    documents: list[DocumentOut] = Field(default_factory=list)


class ProgramCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    category: str | None = None
    country: str = "PK"
    region: str | None = None
    eligibility_rules: list[dict[str, Any]] = Field(default_factory=list)
    required_documents: list[dict[str, Any]] = Field(default_factory=list)
    application_channel: str | None = None
    source_url: str | None = None
    source_date: str | None = None
    effective_date: str | None = None


class ProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    description: str | None
    category: str | None
    country: str
    region: str | None
    eligibility_rules: list[dict[str, Any]]
    required_documents: list[dict[str, Any]]
    application_channel: str | None
    source_url: str | None
    source_date: str | None
    effective_date: str | None


class MatchRunResponse(BaseModel):
    case_id: str
    count: int
    matches: list[MatchOut]


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    program_id: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    due_date: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: str | None = None


class DocumentCreate(BaseModel):
    doc_type: str | None = None
    filename: str | None = None
    status: DocumentStatus = DocumentStatus.RECEIVED
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None


CaseDetail.model_rebuild()


# --------------------------------------------------------------------------- #
# Errors — one consistent envelope for every failure                           #
# --------------------------------------------------------------------------- #


class AppError(Exception):
    code = "error"
    http_status = 400

    def __init__(self, message: str, details: Any = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    code = "not_found"
    http_status = 404


class ConflictError(AppError):
    code = "conflict"
    http_status = 409


def _envelope(code: str, message: str, details: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


# --------------------------------------------------------------------------- #
# Eligibility engine (deterministic)                                           #
# --------------------------------------------------------------------------- #


def _num(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric value")
    return float(value)


OPERATORS = {
    "eq": lambda a, e: a == e,
    "ne": lambda a, e: a != e,
    "lt": lambda a, e: _num(a) < _num(e),
    "lte": lambda a, e: _num(a) <= _num(e),
    "gt": lambda a, e: _num(a) > _num(e),
    "gte": lambda a, e: _num(a) >= _num(e),
    "in": lambda a, e: a in e,
    "not_in": lambda a, e: a not in e,
    "contains": lambda a, e: (e in a) if isinstance(a, (list, tuple, set))
    else (str(e).lower() in a.lower() if isinstance(a, str) else False),
    "between": lambda a, e: _num(e[0]) <= _num(a) <= _num(e[1]),
    "is_true": lambda a, e=None: bool(a) is True,
    "is_false": lambda a, e=None: bool(a) is False,
}


def apply_operator(operator: str, actual: Any, expected: Any = None) -> bool:
    if operator not in OPERATORS:
        raise KeyError(f"Unknown operator: {operator!r}")
    return OPERATORS[operator](actual, expected)


@dataclass
class EvaluatedCondition:
    field: str
    operator: str
    value: Any
    label: str
    required: bool
    status: str
    actual: Any = None
    detail: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchResult:
    match_level: MatchLevel
    score: float
    matched_conditions: list[dict] = field(default_factory=list)
    failed_conditions: list[dict] = field(default_factory=list)
    missing_conditions: list[dict] = field(default_factory=list)


def _evaluate_condition(facts: dict, condition: dict) -> EvaluatedCondition:
    field_name = condition["field"]
    operator = condition["operator"]
    value = condition.get("value")
    label = condition.get("label", f"{field_name} {operator} {value}")
    required = bool(condition.get("required", True))

    if field_name not in facts or facts[field_name] is None:
        return EvaluatedCondition(field_name, operator, value, label, required, "missing")

    actual = facts[field_name]
    try:
        ok = apply_operator(operator, actual, value)
    except (KeyError, ValueError, TypeError) as exc:
        return EvaluatedCondition(
            field_name, operator, value, label, required, "missing", actual,
            detail=f"could not evaluate: {exc}",
        )
    return EvaluatedCondition(
        field_name, operator, value, label, required,
        "matched" if ok else "failed", actual,
    )


def _decide_level(evaluated: list[EvaluatedCondition]) -> MatchLevel:
    if not evaluated:
        return MatchLevel.NEEDS_INFO
    required = [c for c in evaluated if c.required]
    optional = [c for c in evaluated if not c.required]
    if any(c.status == "failed" for c in required):
        return MatchLevel.NOT_ELIGIBLE
    if any(c.status == "missing" for c in required):
        return MatchLevel.NEEDS_INFO
    if any(c.status != "matched" for c in optional):
        return MatchLevel.LIKELY_ELIGIBLE
    return MatchLevel.ELIGIBLE


def evaluate_program(user_facts: dict, eligibility_rules: list[dict]) -> MatchResult:
    """Pure, deterministic: same inputs -> same output."""
    user_facts = user_facts or {}
    eligibility_rules = eligibility_rules or []
    evaluated = [_evaluate_condition(user_facts, c) for c in eligibility_rules]
    matched = [c.to_dict() for c in evaluated if c.status == "matched"]
    failed = [c.to_dict() for c in evaluated if c.status == "failed"]
    missing = [c.to_dict() for c in evaluated if c.status == "missing"]
    total = len(evaluated)
    score = round(len(matched) / total, 3) if total else 0.0
    return MatchResult(_decide_level(evaluated), score, matched, failed, missing)


def resolved_facts(situation: Situation | None) -> dict:
    """Merge typed columns + the flexible facts bag into one dict for matching."""
    if situation is None:
        return {}
    merged = dict(situation.facts or {})
    for key in ("household_size", "monthly_income", "province", "employment_status"):
        value = getattr(situation, key)
        if value is not None:
            merged.setdefault(key, value)
    return merged


# --------------------------------------------------------------------------- #
# Seed data — curated Pakistan program pack (edit/extend freely)               #
# --------------------------------------------------------------------------- #

SEED_PROGRAMS: list[dict] = [
    {
        "code": "BISP_KAFAALAT",
        "name": "Benazir Kafaalat (Unconditional Cash Transfer)",
        "description": "Quarterly cash stipend for the poorest women, identified via the NSER poverty means test.",
        "category": "cash_assistance", "country": "PK", "region": "National",
        "eligibility_rules": [
            {"field": "pmt_score", "operator": "lte", "value": 32, "label": "NSER poverty (PMT) score is 32 or below", "required": True},
            {"field": "has_cnic", "operator": "is_true", "label": "Applicant holds a valid CNIC", "required": True},
            {"field": "gender", "operator": "eq", "value": "female", "label": "Registered beneficiary is a woman", "required": True},
        ],
        "required_documents": [
            {"name": "CNIC", "description": "Valid national identity card of the woman beneficiary"},
            {"name": "NSER registration", "description": "Household registered in the National Socio-Economic Registry"},
        ],
        "application_channel": "BISP Tehsil office / 8171 web portal",
        "source_url": "https://www.bisp.gov.pk/", "source_date": "2025-11-04", "effective_date": "2025-01-01",
    },
    {
        "code": "BISP_TALEEMI_WAZAIF",
        "name": "Benazir Taleemi Wazaif (Education Stipend)",
        "description": "Conditional cash transfer for keeping children (4-22) enrolled and attending school.",
        "category": "education", "country": "PK", "region": "National",
        "eligibility_rules": [
            {"field": "pmt_score", "operator": "lte", "value": 32, "label": "Family qualifies under the Kafaalat poverty threshold", "required": True},
            {"field": "children_in_school", "operator": "gte", "value": 1, "label": "At least one child enrolled in school", "required": True},
            {"field": "has_cnic", "operator": "is_true", "label": "Guardian holds a valid CNIC", "required": True},
        ],
        "required_documents": [
            {"name": "Child B-Form", "description": "Child registration certificate (Form-B)"},
            {"name": "School enrolment proof", "description": "Proof of enrolment and attendance record"},
        ],
        "application_channel": "BISP Tehsil office",
        "source_url": "https://www.bisp.gov.pk/", "source_date": "2025-11-04", "effective_date": "2025-01-01",
    },
    {
        "code": "BISP_NASHONUMA",
        "name": "Benazir Nashonuma Programme (Nutrition)",
        "description": "Conditional cash and nutritious food for pregnant/lactating women and children under two.",
        "category": "nutrition", "country": "PK", "region": "National",
        "eligibility_rules": [
            {"field": "pmt_score", "operator": "lte", "value": 32, "label": "Family qualifies under the poverty threshold", "required": True},
            {"field": "has_pregnant_member", "operator": "is_true", "label": "Household has a pregnant or lactating woman", "required": True},
        ],
        "required_documents": [
            {"name": "CNIC", "description": "Valid national identity card of the woman"},
            {"name": "Pregnancy confirmation", "description": "Health facility confirmation of pregnancy or lactation"},
        ],
        "application_channel": "Nashonuma Facilitation Centre (health facility)",
        "source_url": "https://www.bisp.gov.pk/", "source_date": "2025-11-04", "effective_date": "2025-01-01",
    },
    {
        "code": "PBM_IFA",
        "name": "Pakistan Bait-ul-Mal — Individual Financial Assistance",
        "description": "One-time financial assistance for medical treatment and destitute individuals with no adequate income.",
        "category": "cash_assistance", "country": "PK", "region": "National",
        "eligibility_rules": [
            {"field": "monthly_income", "operator": "lte", "value": 50000, "label": "Monthly household income is PKR 50,000 or below", "required": True},
            {"field": "has_cnic", "operator": "is_true", "label": "Applicant holds a valid CNIC", "required": True},
        ],
        "required_documents": [
            {"name": "CNIC", "description": "Valid national identity card"},
            {"name": "Income proof", "description": "Declaration or evidence of low/no income"},
            {"name": "Medical estimate", "description": "Hospital cost estimate (for medical assistance)"},
        ],
        "application_channel": "Pakistan Bait-ul-Mal district office",
        "source_url": "https://pbm.gov.pk/", "source_date": "2025-06-01", "effective_date": "2025-01-01",
    },
    {
        "code": "SEHAT_SAHULAT",
        "name": "Sehat Sahulat / Sehat Card (Health Coverage)",
        "description": "Micro health insurance giving eligible families cashless treatment at empanelled hospitals.",
        "category": "health", "country": "PK", "region": "Punjab, KP, Gilgit-Baltistan, AJK",
        "eligibility_rules": [
            {"field": "province", "operator": "in", "value": ["Khyber Pakhtunkhwa", "Punjab", "Gilgit-Baltistan", "Azad Jammu and Kashmir"], "label": "Resident of a province where the Sehat Card is active", "required": True},
            {"field": "has_cnic", "operator": "is_true", "label": "Family head holds a valid CNIC", "required": True},
        ],
        "required_documents": [
            {"name": "CNIC", "description": "Valid national identity card of the family head"},
        ],
        "application_channel": "Empanelled hospital Sehat Card desk",
        "source_url": "https://www.sehatsahulat.com.pk/", "source_date": "2025-06-01", "effective_date": "2025-01-01",
    },
    {
        "code": "PUNJAB_HIMMAT",
        "name": "Punjab Himmat Card (Persons with Disabilities)",
        "description": "Quarterly cash assistance for registered persons with disabilities in Punjab unable to earn a livelihood.",
        "category": "disability", "country": "PK", "region": "Punjab",
        "eligibility_rules": [
            {"field": "province", "operator": "eq", "value": "Punjab", "label": "Resident of Punjab", "required": True},
            {"field": "has_disability", "operator": "is_true", "label": "Registered person with a disability", "required": True},
            {"field": "has_cnic", "operator": "is_true", "label": "Holds a CNIC with disability status", "required": True},
        ],
        "required_documents": [
            {"name": "Disability certificate", "description": "Assessment certificate from the Social Welfare department"},
            {"name": "CNIC", "description": "CNIC endorsed with disability logo"},
        ],
        "application_channel": "Punjab Social Protection Authority",
        "source_url": "https://pspa.punjab.gov.pk/", "source_date": "2025-06-01", "effective_date": "2025-01-01",
    },
    {
        "code": "EOBI_OLD_AGE",
        "name": "EOBI Old-Age Pension",
        "description": "Monthly pension for registered private-sector workers who reached retirement age and completed minimum service.",
        "category": "pension", "country": "PK", "region": "National",
        "eligibility_rules": [
            {"field": "age", "operator": "gte", "value": 60, "label": "Age 60 or above (55 for women)", "required": True},
            {"field": "eobi_registered", "operator": "is_true", "label": "Registered with EOBI as an insured worker", "required": True},
            {"field": "insured_years", "operator": "gte", "value": 15, "label": "At least 15 years of insurable employment", "required": True},
        ],
        "required_documents": [
            {"name": "CNIC", "description": "Valid national identity card"},
            {"name": "EOBI registration", "description": "EOBI insured-person registration number"},
            {"name": "Service record", "description": "Proof of contributory service"},
        ],
        "application_channel": "EOBI regional office",
        "source_url": "https://www.eobi.gov.pk/", "source_date": "2025-06-01", "effective_date": "2025-01-01",
    },
    {
        "code": "PUNJAB_RASHAN",
        "name": "Punjab Rashan / Subsidised Food Support",
        "description": "Targeted subsidy on essential food items for low-income households registered in Punjab.",
        "category": "nutrition", "country": "PK", "region": "Punjab",
        "eligibility_rules": [
            {"field": "province", "operator": "eq", "value": "Punjab", "label": "Resident of Punjab", "required": True},
            {"field": "monthly_income", "operator": "lte", "value": 60000, "label": "Monthly household income is PKR 60,000 or below", "required": True},
            {"field": "has_cnic", "operator": "is_true", "label": "Applicant holds a valid CNIC", "required": True},
        ],
        "required_documents": [
            {"name": "CNIC", "description": "Valid national identity card"},
        ],
        "application_channel": "Registered retailer / provincial food portal",
        "source_url": "https://punjab.gov.pk/social-welfare-and-protection", "source_date": "2025-06-01", "effective_date": "2025-01-01",
    },
]


def seed_programs(db: Session) -> int:
    for item in SEED_PROGRAMS:
        existing = db.scalar(select(Program).where(Program.code == item["code"]))
        if existing is None:
            db.add(Program(**item))
        else:
            for key, value in item.items():
                setattr(existing, key, value)
    db.commit()
    return len(SEED_PROGRAMS)


# --------------------------------------------------------------------------- #
# FastAPI app + lifespan (create tables, seed programs)                        #
# --------------------------------------------------------------------------- #


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_programs(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="HaqFlow Backend",
    version="0.1.0",
    description="Cases, programs, deterministic eligibility engine, tasks, and evidence.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def _app_error(_, exc: AppError):
    return JSONResponse(
        status_code=exc.http_status,
        content=_envelope(exc.code, exc.message, exc.details),
    )


@app.exception_handler(RequestValidationError)
async def _validation_error(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_envelope("validation_error", "Request validation failed.", exc.errors()),
    )


@app.exception_handler(StarletteHTTPException)
async def _http_error(_, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content=_envelope("http_error", str(exc.detail)))


@app.exception_handler(Exception)
async def _unhandled(_, exc: Exception):
    return JSONResponse(status_code=500, content=_envelope("internal_error", "An unexpected error occurred."))


# --------------------------------------------------------------------------- #
# Helper: upsert a situation                                                   #
# --------------------------------------------------------------------------- #


def _get_case(db: Session, case_id: str) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id!r} not found.")
    return case


def _upsert_situation(db: Session, case: Case, payload: SituationIn) -> Situation:
    situation = case.situation
    if situation is None:
        situation = Situation(case_id=case.id)
        db.add(situation)
    situation.household_size = payload.household_size
    situation.monthly_income = payload.monthly_income
    situation.province = payload.province
    situation.employment_status = payload.employment_status
    situation.facts = payload.facts or {}
    db.flush()
    return situation


# --------------------------------------------------------------------------- #
# Routes — meta                                                                #
# --------------------------------------------------------------------------- #


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "HaqFlow Backend", "version": "0.1.0"}


@app.get("/", tags=["meta"])
def root():
    return {"service": "HaqFlow Backend", "docs": "/docs", "health": "/health"}


# --------------------------------------------------------------------------- #
# Routes — cases & situation                                                   #
# --------------------------------------------------------------------------- #


@app.post("/cases", response_model=CaseDetail, status_code=201, tags=["cases"])
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    case = Case(raw_text=payload.raw_text, language=payload.language, summary=payload.summary)
    db.add(case)
    db.flush()
    if payload.situation is not None:
        _upsert_situation(db, case, payload.situation)
    db.commit()
    db.refresh(case)
    return CaseDetail.model_validate(case)


@app.get("/cases", response_model=list[CaseSummary], tags=["cases"])
def list_cases(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db)):
    stmt = select(Case).order_by(Case.created_at.desc()).limit(limit).offset(offset)
    return [CaseSummary.model_validate(c) for c in db.scalars(stmt).all()]


@app.get("/cases/{case_id}", response_model=CaseDetail, tags=["cases"])
def get_case(case_id: str, db: Session = Depends(get_db)):
    return CaseDetail.model_validate(_get_case(db, case_id))


@app.put("/cases/{case_id}/situation", response_model=SituationOut, tags=["cases"])
def set_situation(case_id: str, payload: SituationIn, db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    situation = _upsert_situation(db, case, payload)
    db.commit()
    db.refresh(situation)
    return SituationOut.model_validate(situation)


# --------------------------------------------------------------------------- #
# Routes — programs                                                            #
# --------------------------------------------------------------------------- #


@app.post("/programs", response_model=ProgramOut, status_code=201, tags=["programs"])
def create_program(payload: ProgramCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Program).where(Program.code == payload.code)) is not None:
        raise ConflictError(f"Program with code {payload.code!r} already exists.")
    program = Program(**payload.model_dump())
    db.add(program)
    db.commit()
    db.refresh(program)
    return ProgramOut.model_validate(program)


@app.get("/programs", response_model=list[ProgramOut], tags=["programs"])
def list_programs(country: str | None = None, category: str | None = None,
                  limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db)):
    stmt = select(Program).order_by(Program.name)
    if country:
        stmt = stmt.where(Program.country == country)
    if category:
        stmt = stmt.where(Program.category == category)
    stmt = stmt.limit(limit).offset(offset)
    return [ProgramOut.model_validate(p) for p in db.scalars(stmt).all()]


@app.get("/programs/{program_id}", response_model=ProgramOut, tags=["programs"])
def get_program(program_id: str, db: Session = Depends(get_db)):
    program = db.get(Program, program_id)
    if program is None:
        raise NotFoundError(f"Program {program_id!r} not found.")
    return ProgramOut.model_validate(program)


# --------------------------------------------------------------------------- #
# Routes — matches (the eligibility engine)                                    #
# --------------------------------------------------------------------------- #


@app.post("/cases/{case_id}/match", response_model=MatchRunResponse, tags=["matches"])
def run_matches(case_id: str, db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    facts = resolved_facts(case.situation)
    programs = db.scalars(select(Program)).all()
    db.execute(delete(Match).where(Match.case_id == case_id))  # clear stale results
    created: list[Match] = []
    for program in programs:
        result = evaluate_program(facts, program.eligibility_rules or [])
        match = Match(
            case_id=case_id, program_id=program.id,
            match_level=result.match_level.value, score=result.score,
            matched_conditions=result.matched_conditions,
            failed_conditions=result.failed_conditions,
            missing_conditions=result.missing_conditions,
        )
        db.add(match)
        created.append(match)
    db.commit()
    for m in created:
        db.refresh(m)
    created.sort(key=lambda m: m.score, reverse=True)  # best matches first
    return MatchRunResponse(
        case_id=case_id, count=len(created),
        matches=[MatchOut.model_validate(m) for m in created],
    )


@app.get("/cases/{case_id}/matches", response_model=list[MatchOut], tags=["matches"])
def list_matches(case_id: str, db: Session = Depends(get_db)):
    _get_case(db, case_id)
    stmt = select(Match).where(Match.case_id == case_id).order_by(Match.score.desc())
    return [MatchOut.model_validate(m) for m in db.scalars(stmt).all()]


# --------------------------------------------------------------------------- #
# Routes — tasks (action plan)                                                 #
# --------------------------------------------------------------------------- #


@app.post("/cases/{case_id}/tasks", response_model=TaskOut, status_code=201, tags=["tasks"])
def create_task(case_id: str, payload: TaskCreate, db: Session = Depends(get_db)):
    _get_case(db, case_id)
    task = Task(
        case_id=case_id, program_id=payload.program_id, title=payload.title,
        description=payload.description, status=payload.status.value,
        priority=payload.priority.value, due_date=payload.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task)


@app.get("/cases/{case_id}/tasks", response_model=list[TaskOut], tags=["tasks"])
def list_tasks(case_id: str, db: Session = Depends(get_db)):
    _get_case(db, case_id)
    stmt = select(Task).where(Task.case_id == case_id).order_by(Task.created_at.asc())
    return [TaskOut.model_validate(t) for t in db.scalars(stmt).all()]


@app.patch("/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
def update_task(task_id: str, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise NotFoundError(f"Task {task_id!r} not found.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") is not None:
        task.status = data["status"].value
    if data.get("priority") is not None:
        task.priority = data["priority"].value
    for f in ("title", "description", "due_date"):
        if f in data:
            setattr(task, f, data[f])
    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task)


@app.get("/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise NotFoundError(f"Task {task_id!r} not found.")
    return TaskOut.model_validate(task)


# --------------------------------------------------------------------------- #
# Routes — documents (evidence)                                                #
# --------------------------------------------------------------------------- #


@app.post("/cases/{case_id}/documents", response_model=DocumentOut, status_code=201, tags=["documents"])
def create_document(case_id: str, payload: DocumentCreate, db: Session = Depends(get_db)):
    _get_case(db, case_id)
    document = Document(
        case_id=case_id, doc_type=payload.doc_type, filename=payload.filename,
        status=payload.status.value, extracted_fields=payload.extracted_fields,
        confidence=payload.confidence, notes=payload.notes,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return DocumentOut.model_validate(document)


@app.get("/cases/{case_id}/documents", response_model=list[DocumentOut], tags=["documents"])
def list_documents(case_id: str, db: Session = Depends(get_db)):
    _get_case(db, case_id)
    stmt = select(Document).where(Document.case_id == case_id).order_by(Document.created_at.asc())
    return [DocumentOut.model_validate(d) for d in db.scalars(stmt).all()]


# --------------------------------------------------------------------------- #
# Allow `python app.py` to launch the server directly.                         #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
