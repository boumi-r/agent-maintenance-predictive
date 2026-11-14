"""Configuration centralisée, lue depuis les variables d'environnement (voir .env.example)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    # Base de données
    database_url: str = "sqlite:///./maintenance.db"

    # Agent Claude
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_max_tokens: int = Field(default=2048, ge=256)
    agent_max_iterations: int = Field(default=8, ge=1, le=20)

    # Authentification
    jwt_secret: SecretStr = SecretStr("change-me-dev-only")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, ge=1)
    api_key_salt: SecretStr = SecretStr("change-me-dev-only")

    # HTTP
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"]
    )
    rate_limit_analyse: str = "10/minute"

    # Email
    email_provider: Literal["sendgrid", "resend", "console"] = "console"
    email_from: str = "alertes@example.com"
    email_from_name: str = "MaintenanceAI"
    sendgrid_api_key: SecretStr = SecretStr("")
    resend_api_key: SecretStr = SecretStr("")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _normaliser_postgres(cls, value: str) -> str:
        # Railway fournit postgres:// ou postgresql:// ; SQLAlchemy 2 + psycopg 3 veut postgresql+psycopg://
        for prefixe in ("postgres://", "postgresql://"):
            if value.startswith(prefixe):
                return "postgresql+psycopg://" + value[len(prefixe) :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
