"""Program persistence and lookup."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Program
from app.schemas import ProgramCreate
from app.utils.errors import ConflictError, NotFoundError


def create_program(db: Session, payload: ProgramCreate) -> Program:
    existing = db.scalar(select(Program).where(Program.code == payload.code))
    if existing is not None:
        raise ConflictError(f"Program with code {payload.code!r} already exists.")

    program = Program(**payload.model_dump())
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


def get_program(db: Session, program_id: str) -> Program:
    program = db.get(Program, program_id)
    if program is None:
        raise NotFoundError(f"Program {program_id!r} not found.")
    return program


def list_programs(
    db: Session,
    country: str | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Program]:
    stmt = select(Program).order_by(Program.name)
    if country:
        stmt = stmt.where(Program.country == country)
    if category:
        stmt = stmt.where(Program.category == category)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def upsert_by_code(db: Session, payload: ProgramCreate) -> Program:
    """Insert, or update in place when a program with the code exists.

    Used by the seeder so re-running it is safe.
    """
    program = db.scalar(select(Program).where(Program.code == payload.code))
    data = payload.model_dump()
    if program is None:
        program = Program(**data)
        db.add(program)
    else:
        for key, value in data.items():
            setattr(program, key, value)
    db.flush()
    return program
