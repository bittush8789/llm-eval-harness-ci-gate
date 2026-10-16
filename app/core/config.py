"""Centralized application configuration using Pydantic Settings."""

import hashlib
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and evaluation platform configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment & Server
    ENVIRONMENT: str = Field(default="development", description="Application environment")
    APP_HOST: str = Field(default="0.0.0.0", description="API host")
    APP_PORT: int = Field(default=8000, description="API port")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ai_evaluation",
        description="Database connection URL",
    )
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_DB: str = Field(default="ai_evaluation")
    POSTGRES_PORT: int = Field(default=5432)

    # Google Gemini API
    GOOGLE_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API Key",
    )

    # Target Application Model Settings
    APP_LLM_MODEL: str = Field(
        default="gemini-3.8-flash",
        description="LangChain Gemini model for application answers",
    )
    APP_LLM_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=1.0)
    APP_PROMPT_VERSION: str = Field(default="v1.0.0")
    PROMPT_FILE_PATH: str = Field(default="app/prompts/system_prompt.txt")

    # Evaluator Judge Model Settings (Configured independently from target model)
    EVALUATOR_LLM_MODEL: str = Field(
        default="gemini-3.8-pro",
        description="Model identifier for Ragas/LLM judge evaluator",
    )
    EVALUATOR_LLM_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=1.0)
    EVALUATION_OFFLINE_MODE: bool = Field(
        default=False,
        description="When True, uses deterministic mock evaluations without external API calls",
    )
    EVALUATION_THRESHOLDS_FILE: str = Field(default="evaluation/thresholds.yaml")
    DEFAULT_DATASET_VERSION: str = Field(default="v1")
    EVALUATION_MAX_RETRIES: int = Field(default=2, ge=0, le=5)
    EVALUATION_TIMEOUT_SECONDS: int = Field(default=30, ge=5, le=120)

    # Optional LangSmith Tracing
    LANGCHAIN_TRACING_V2: bool = Field(default=False)
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com")
    LANGCHAIN_API_KEY: Optional[str] = Field(default=None)
    LANGCHAIN_PROJECT: str = Field(default="ai-evaluation-regression-platform")

    def get_system_prompt_content(self) -> str:
        """Read system prompt text from the configured prompt file."""
        path = Path(self.PROMPT_FILE_PATH)
        if not path.is_file():
            # Try workspace root fallback
            alt_path = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"
            if alt_path.is_file():
                path = alt_path
            else:
                return (
                    "You are a helpful AI assistant. Answer questions strictly based "
                    "on the provided context and cite sources."
                )
        return path.read_text(encoding="utf-8").strip()

    def get_prompt_hash(self) -> str:
        """Compute SHA256 hash of system prompt file content for regression tracking."""
        content = self.get_system_prompt_content()
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


settings = Settings()
