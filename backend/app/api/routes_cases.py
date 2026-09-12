"""Case + situation endpoints. Handlers stay thin: validate -> service -> schema."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CaseCreate, CaseDetail, CaseSummary, SituationIn, SituationOut
from app.services import case_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseDetail, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)) -> CaseDetail:
    case = case_service.create_case(db, payload)
    return CaseDetail.model_validate(case)


@router.get("", response_model=list[CaseSummary])
def list_cases(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[CaseSummary]:
    cases = case_service.list_cases(db, limit=limit, offset=offset)
    return [CaseSummary.model_validate(c) for c in cases]


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, db: Session = Depends(get_db)) -> CaseDetail:
    case = case_service.get_case(db, case_id)
    return CaseDetail.model_validate(case)


@router.put("/{case_id}/situation", response_model=SituationOut)
def set_situation(
    case_id: str, payload: SituationIn, db: Session = Depends(get_db)
) -> SituationOut:
    situation = case_service.set_situation(db, case_id, payload)
    return SituationOut.model_validate(situation)
