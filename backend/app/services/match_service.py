"""Run the eligibility engine over a case and persist the results."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Match, Program
from app.rules import evaluate_program
from app.services import case_service, program_service


def run_matches(db: Session, case_id: str) -> list[Match]:
    """Evaluate the case's situation against every relevant program.

    Previous matches for the case are cleared first so results always reflect
    the current situation (idempotent re-run after new facts arrive).
    """
    case = case_service.get_case(db, case_id)
    facts = case_service.resolved_facts(case.situation)

    programs = program_service.list_programs(db, country=None, limit=1000)

    # Clear stale matches for this case.
    db.execute(delete(Match).where(Match.case_id == case_id))

    created: list[Match] = []
    for program in programs:
        result = evaluate_program(facts, program.eligibility_rules or [])
        match = Match(
            case_id=case_id,
            program_id=program.id,
            match_level=result.match_level.value,
            score=result.score,
            matched_conditions=result.matched_conditions,
            failed_conditions=result.failed_conditions,
            missing_conditions=result.missing_conditions,
        )
        db.add(match)
        created.append(match)

    db.commit()
    for match in created:
        db.refresh(match)

    # Best matches first (highest score), stable and useful for the frontend.
    created.sort(key=lambda m: m.score, reverse=True)
    return created


def list_matches(db: Session, case_id: str) -> list[Match]:
    case_service.get_case(db, case_id)  # ensures 404 if the case is missing
    stmt = (
        select(Match)
        .where(Match.case_id == case_id)
        .order_by(Match.score.desc())
    )
    return list(db.scalars(stmt).all())


def evaluate_single(db: Session, case_id: str, program_id: str) -> Match:
    """Evaluate one case against one program without persisting (utility)."""
    case = case_service.get_case(db, case_id)
    program: Program = program_service.get_program(db, program_id)
    facts = case_service.resolved_facts(case.situation)
    result = evaluate_program(facts, program.eligibility_rules or [])
    return Match(
        case_id=case_id,
        program_id=program_id,
        match_level=result.match_level.value,
        score=result.score,
        matched_conditions=result.matched_conditions,
        failed_conditions=result.failed_conditions,
        missing_conditions=result.missing_conditions,
    )
