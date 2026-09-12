"""Case and situation persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Case, Situation
from app.schemas import CaseCreate, SituationIn
from app.utils.errors import NotFoundError


def create_case(db: Session, payload: CaseCreate) -> Case:
    case = Case(
        raw_text=payload.raw_text,
        language=payload.language,
        summary=payload.summary,
    )
    db.add(case)
    db.flush()  # assigns case.id

    if payload.situation is not None:
        _upsert_situation(db, case, payload.situation)

    db.commit()
    db.refresh(case)
    return case


def get_case(db: Session, case_id: str) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id!r} not found.")
    return case


def list_cases(db: Session, limit: int = 50, offset: int = 0) -> list[Case]:
    stmt = (
        select(Case)
        .order_by(Case.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())


def set_situation(db: Session, case_id: str, payload: SituationIn) -> Situation:
    """Create or replace a case's structured situation (idempotent upsert)."""
    case = get_case(db, case_id)
    situation = _upsert_situation(db, case, payload)
    db.commit()
    db.refresh(situation)
    return situation


def _upsert_situation(
    db: Session, case: Case, payload: SituationIn
) -> Situation:
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


def resolved_facts(situation: Situation | None) -> dict:
    """Merge typed columns and the flexible ``facts`` bag into one dict.

    Typed columns win only when set, so the AI can pass either the named
    columns or the same keys inside ``facts`` and matching still works.
    """
    if situation is None:
        return {}
    merged: dict = dict(situation.facts or {})
    for key in ("household_size", "monthly_income", "province", "employment_status"):
        value = getattr(situation, key)
        if value is not None:
            merged.setdefault(key, value)
    return merged
