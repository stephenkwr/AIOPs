"""Application configuration.

12-factor: every setting comes from the environment (or backend/.env locally).
No environment-specific branching in code — behaviour is driven entirely by values.
"""

from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "local"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/copilot"
    # Direct (non-pooled) connection used for migrations. Falls back to database_url.
    database_url_direct: str | None = None

    # CORS: comma-separated list of allowed origins.
    cors_origins: str = "http://localhost:3000"

    # LLM providers (optional until Phase 1+).
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Model selection.
    agent_model: str = "gemini-2.5-flash"
    judge_model: str = "llama-3.3-70b-versatile"
    embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768

    @cached_property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @cached_property
    def migration_url(self) -> str:
        return self.database_url_direct or self.database_url


settings = Settings()
