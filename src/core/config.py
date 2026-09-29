from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project Information
    PROJECT_NAME: str = "Enterprise Knowledge & Operations Intelligence Platform"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True

    # Database Configuration (PostgreSQL 16 + pgvector)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_rag",
        description="Async SQLAlchemy database connection URI",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_async_db_url(cls, v: str) -> str:
        """Ensures the connection URI uses asyncpg driver on Render, Heroku, or standard cloud."""
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # JWT & Security Configuration
    JWT_SECRET_KEY: str = Field(
        default="development-insecure-secret-key-change-in-production-min32bytes",
        description="Secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # AI Model Provider Configuration
    GEMINI_API_KEY: str = Field(
        ...,
        description="Google Gemini API Key for LLM and Embedding services",
    )
    ACTIVE_EMBEDDING_MODEL: str = Field(
        default="gemini-embedding-001",
        description="Active embedding model used for chunk vectorization",
    )
    EMBEDDING_DIMENSION: int = Field(
        default=768,
        description="Dimensionality of vectors produced by the active embedding model",
    )
    UPLOAD_DIR: str = Field(
        default="data/uploads",
        description="Local directory for raw uploaded document storage",
    )
    ACTIVE_LLM_MODEL: str = Field(
        default="gemini-3.5-flash-lite",
        description="Active Gemini LLM model for text completion and RAG answers",
    )

    # Observability & Tracing Configuration (Langfuse)
    LANGFUSE_PUBLIC_KEY: str | None = Field(
        default=None,
        description="Langfuse public API key for LLM tracing and analytics",
    )
    LANGFUSE_SECRET_KEY: str | None = Field(
        default=None,
        description="Langfuse secret API key for LLM tracing and analytics",
    )
    LANGFUSE_HOST: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse server host URL (Cloud or self-hosted)",
    )
    LANGFUSE_ENABLED: bool = Field(
        default=False,
        description="Flag to toggle Langfuse observability integration",
    )


@lru_cache
def get_settings() -> Settings:
    """Returns a cached singleton instance of application settings."""
    return Settings()
