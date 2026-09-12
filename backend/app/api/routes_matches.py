"""Eligibility match endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MatchOut, MatchRunResponse
from app.services import match_service

router = APIRouter(prefix="/cases", tags=["matches"])


@router.post("/{case_id}/match", response_model=MatchRunResponse)
def run_matches(case_id: str, db: Session = Depends(get_db)) -> MatchRunResponse:
    """Run the deterministic eligibility engine over all programs for a case."""
    matches = match_service.run_matches(db, case_id)
    return MatchRunResponse(
        case_id=case_id,
        count=len(matches),
        matches=[MatchOut.model_validate(m) for m in matches],
    )


@router.get("/{case_id}/matches", response_model=list[MatchOut])
def list_matches(case_id: str, db: Session = Depends(get_db)) -> list[MatchOut]:
    matches = match_service.list_matches(db, case_id)
    return [MatchOut.model_validate(m) for m in matches]
