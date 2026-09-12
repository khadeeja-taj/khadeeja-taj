"""Application configuration.

Reads settings from environment variables (and an optional ``.env`` file).
The backend defaults to a local SQLite database so it runs with zero external
setup during the hackathon, but ``DATABASE_URL`` can point at Supabase /
PostgreSQL for a shared team database — nothing else in the code changes.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "HaqFlow Backend"
    environment: str = "development"

    # SQLite by default; override with a Postgres/Supabase URL, e.g.
    #   postgresql+psycopg2://user:pass@host:5432/dbname
    database_url: str = "sqlite:///./haqflow.db"

    # Whether to auto-create tables and seed programs on startup.
    auto_create_tables: bool = True
    auto_seed_programs: bool = True

    # CORS origins for the frontend (Member 4).
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
