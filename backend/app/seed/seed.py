"""Load the curated Pakistan program pack into the database.

Idempotent: safe to run on every startup. Can also be run directly::

    python -m app.seed.seed
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal, create_all
from app.schemas import ProgramCreate
from app.services import program_service

_PROGRAMS_FILE = Path(__file__).with_name("programs.json")


def load_program_payloads() -> list[ProgramCreate]:
    data = json.loads(_PROGRAMS_FILE.read_text(encoding="utf-8"))
    return [ProgramCreate(**item) for item in data]


def seed_programs(db: Session) -> int:
    """Insert or update all seed programs. Returns the number processed."""
    payloads = load_program_payloads()
    for payload in payloads:
        program_service.upsert_by_code(db, payload)
    db.commit()
    return len(payloads)


def main() -> None:
    create_all()
    db = SessionLocal()
    try:
        count = seed_programs(db)
        print(f"Seeded {count} programs.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
