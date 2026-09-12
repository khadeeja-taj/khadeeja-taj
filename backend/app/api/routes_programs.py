"""Program endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ProgramCreate, ProgramOut
from app.services import program_service

router = APIRouter(prefix="/programs", tags=["programs"])


@router.post("", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
def create_program(
    payload: ProgramCreate, db: Session = Depends(get_db)
) -> ProgramOut:
    program = program_service.create_program(db, payload)
    return ProgramOut.model_validate(program)


@router.get("", response_model=list[ProgramOut])
def list_programs(
    country: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[ProgramOut]:
    programs = program_service.list_programs(
        db, country=country, category=category, limit=limit, offset=offset
    )
    return [ProgramOut.model_validate(p) for p in programs]


@router.get("/{program_id}", response_model=ProgramOut)
def get_program(program_id: str, db: Session = Depends(get_db)) -> ProgramOut:
    program = program_service.get_program(db, program_id)
    return ProgramOut.model_validate(program)
