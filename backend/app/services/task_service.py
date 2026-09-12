"""Action-plan task persistence and status updates."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task
from app.schemas import TaskCreate, TaskUpdate
from app.services import case_service
from app.utils.errors import NotFoundError


def create_task(db: Session, case_id: str, payload: TaskCreate) -> Task:
    case_service.get_case(db, case_id)  # 404 if the case does not exist
    task = Task(
        case_id=case_id,
        program_id=payload.program_id,
        title=payload.title,
        description=payload.description,
        status=payload.status.value,
        priority=payload.priority.value,
        due_date=payload.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, case_id: str) -> list[Task]:
    case_service.get_case(db, case_id)
    stmt = (
        select(Task)
        .where(Task.case_id == case_id)
        .order_by(Task.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def get_task(db: Session, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise NotFoundError(f"Task {task_id!r} not found.")
    return task


def update_task(db: Session, task_id: str, payload: TaskUpdate) -> Task:
    task = get_task(db, task_id)
    data = payload.model_dump(exclude_unset=True)

    if "status" in data and data["status"] is not None:
        task.status = data["status"].value
    if "priority" in data and data["priority"] is not None:
        task.priority = data["priority"].value
    for field_name in ("title", "description", "due_date"):
        if field_name in data:
            setattr(task, field_name, data[field_name])

    db.commit()
    db.refresh(task)
    return task
