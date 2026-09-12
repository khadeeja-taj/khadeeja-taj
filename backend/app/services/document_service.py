"""Document/evidence result persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document
from app.schemas import DocumentCreate
from app.services import case_service


def create_document(
    db: Session, case_id: str, payload: DocumentCreate
) -> Document:
    case_service.get_case(db, case_id)  # 404 if the case does not exist
    document = Document(
        case_id=case_id,
        doc_type=payload.doc_type,
        filename=payload.filename,
        status=payload.status.value,
        extracted_fields=payload.extracted_fields,
        confidence=payload.confidence,
        notes=payload.notes,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session, case_id: str) -> list[Document]:
    case_service.get_case(db, case_id)
    stmt = (
        select(Document)
        .where(Document.case_id == case_id)
        .order_by(Document.created_at.asc())
    )
    return list(db.scalars(stmt).all())
