"""Pydantic v2 schemas.

Every endpoint validates input and serializes output through these models, so
API handlers never return ad-hoc dictionaries and field names stay stable
across the team.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CaseStatus,
    DocumentStatus,
    MatchLevel,
    TaskPriority,
    TaskStatus,
)

# --------------------------------------------------------------------------- #
# Situation                                                                    #
# --------------------------------------------------------------------------- #


class SituationIn(BaseModel):
    """Structured facts written by the AI intake agent (Member 1/3)."""

    household_size: int | None = Field(default=None, ge=0)
    monthly_income: float | None = Field(default=None, ge=0)
    province: str | None = None
    employment_status: str | None = None
    # Everything else the engine should consider (pmt_score, has_disability,
    # has_pregnant_member, children_in_school, age, has_cnic, ...).
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


# --------------------------------------------------------------------------- #
# Case                                                                         #
# --------------------------------------------------------------------------- #


class CaseCreate(BaseModel):
    raw_text: str | None = Field(default=None, description="Original problem text")
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


class CaseDetail(CaseSummary):
    raw_text: str | None
    situation: SituationOut | None = None
    matches: list["MatchOut"] = Field(default_factory=list)
    tasks: list["TaskOut"] = Field(default_factory=list)
    documents: list["DocumentOut"] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Program                                                                      #
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Match                                                                        #
# --------------------------------------------------------------------------- #


class ConditionOut(BaseModel):
    field: str
    operator: str
    value: Any = None
    label: str
    required: bool
    status: str
    actual: Any = None
    detail: str | None = None


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


class MatchRunResponse(BaseModel):
    case_id: str
    count: int
    matches: list[MatchOut]


# --------------------------------------------------------------------------- #
# Task (ActionItem)                                                            #
# --------------------------------------------------------------------------- #


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    program_id: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    due_date: str | None = None


class TaskUpdate(BaseModel):
    """Partial update — only provided fields change."""

    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: str | None = None


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


# --------------------------------------------------------------------------- #
# Document                                                                     #
# --------------------------------------------------------------------------- #


class DocumentCreate(BaseModel):
    doc_type: str | None = None
    filename: str | None = None
    status: DocumentStatus = DocumentStatus.RECEIVED
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None


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


# --------------------------------------------------------------------------- #
# Errors                                                                       #
# --------------------------------------------------------------------------- #


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# Resolve forward references for nested models.
CaseDetail.model_rebuild()
