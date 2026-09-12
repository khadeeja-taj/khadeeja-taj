"""Service layer: all database access and business logic live here.

Route handlers stay thin (validate -> call service -> return schema); database
calls never appear directly in route files.
"""

from app.services import (
    case_service,
    document_service,
    match_service,
    program_service,
    task_service,
)

__all__ = [
    "case_service",
    "program_service",
    "match_service",
    "task_service",
    "document_service",
]
