"""HaqFlow backend application entrypoint.

Run locally with::

    uvicorn app.main:app --reload

Interactive API docs are then available at http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import get_settings
from app.database import SessionLocal, create_all
from app.utils.errors import register_exception_handlers

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup: create tables and seed the curated program pack if configured.
    if settings.auto_create_tables:
        create_all()
    if settings.auto_seed_programs:
        from app.seed import seed_programs

        db = SessionLocal()
        try:
            seed_programs(db)
        finally:
            db.close()
    yield
    # Shutdown: nothing to tear down for the hackathon build.


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "HaqFlow backend — cases, programs, deterministic eligibility engine, "
        "action-plan tasks and evidence persistence."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "version": "0.1.0"}


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "health": "/health",
    }
