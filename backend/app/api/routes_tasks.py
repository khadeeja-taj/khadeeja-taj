"""Action-plan task endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import TaskCreate, TaskOut, TaskUpdate
from app.services import task_service

# Tasks are nested under a case for creation/listing.
case_router = APIRouter(prefix="/cases", tags=["tasks"])
# Direct access for status updates by task id.
task_router = APIRouter(prefix="/tasks", tags=["tasks"])


@case_router.post(
    "/{case_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED
)
def create_task(
    case_id: str, payload: TaskCreate, db: Session = Depends(get_db)
) -> TaskOut:
    task = task_service.create_task(db, case_id, payload)
    return TaskOut.model_validate(task)


@case_router.get("/{case_id}/tasks", response_model=list[TaskOut])
def list_tasks(case_id: str, db: Session = Depends(get_db)) -> list[TaskOut]:
    tasks = task_service.list_tasks(db, case_id)
    return [TaskOut.model_validate(t) for t in tasks]


@task_router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str, payload: TaskUpdate, db: Session = Depends(get_db)
) -> TaskOut:
    task = task_service.update_task(db, task_id, payload)
    return TaskOut.model_validate(task)


@task_router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db)) -> TaskOut:
    task = task_service.get_task(db, task_id)
    return TaskOut.model_validate(task)


# Combined router imported by app.api package.
router = APIRouter()
router.include_router(case_router)
router.include_router(task_router)
