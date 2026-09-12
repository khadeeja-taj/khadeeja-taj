"""Document/evidence endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import DocumentCreate, DocumentOut
from app.services import document_service

router = APIRouter(prefix="/cases", tags=["documents"])


@router.post(
    "/{case_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    case_id: str, payload: DocumentCreate, db: Session = Depends(get_db)
) -> DocumentOut:
    document = document_service.create_document(db, case_id, payload)
    return DocumentOut.model_validate(document)


@router.get("/{case_id}/documents", response_model=list[DocumentOut])
def list_documents(
    case_id: str, db: Session = Depends(get_db)
) -> list[DocumentOut]:
    documents = document_service.list_documents(db, case_id)
    return [DocumentOut.model_validate(d) for d in documents]
