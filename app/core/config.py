from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        """Synchronous URL used by Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Portal credentials ────────────────────────────────────────────────────
    portal_url: str
    portal_username: str
    portal_password: str

    # ── Selenium ──────────────────────────────────────────────────────────────
    selenium_remote_url: str = "http://selenium:4444/wd/hub"
    selenium_timeout_seconds: int = 30
    selenium_headless: bool = True

    # ── RPA concurrency ───────────────────────────────────────────────────────
    rpa_max_workers: int = 2

    # ── Application ───────────────────────────────────────────────────────────
    log_level: str = "INFO"
    app_env: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
