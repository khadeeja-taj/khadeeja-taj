"""API routers."""

from fastapi import APIRouter

from app.api import (
    routes_cases,
    routes_documents,
    routes_matches,
    routes_programs,
    routes_tasks,
)

api_router = APIRouter()
api_router.include_router(routes_cases.router)
api_router.include_router(routes_programs.router)
api_router.include_router(routes_matches.router)
api_router.include_router(routes_tasks.router)
api_router.include_router(routes_documents.router)

__all__ = ["api_router"]
