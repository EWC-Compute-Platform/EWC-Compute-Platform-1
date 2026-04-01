"""
EWC Compute — Application settings.

All configuration is read from environment variables or a .env file.
pydantic-settings validates types and raises on startup if required vars are missing.

Phase notes:
  - Phase 0: APP_*, JWT_*, MONGODB_*, REDIS_* are required.
  - Phase 1: NIM_* vars are required. ANTHROPIC_API_KEY is optional fallback.
  - Phase 2: PHYSICSNEMO_* paths and solver API vars become required.
  - Phase 3: OMNIVERSE_*, OVPHYSX_ENDPOINT become required.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # Silently ignore unknown env vars
    )

    # ── Application ──────────────────────────────────────────────────────
    APP_ENV: Literal["development", "test", "staging", "production"] = "development"
    APP_VERSION: str = "0.1.0"
    APP_SECRET_KEY: str = Field(..., min_length=32)
    APP_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("APP_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v: str | list[str]) -> list[str]:
        """Accept comma-separated string or list from environment."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ── Authentication ────────────────────────────────────────────────────
    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ──────────────────────────────────────────────────────────
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "ewc_compute_dev"

    # ── Redis / Job queue ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── NVIDIA NIM — Phase 1 ──────────────────────────────────────────────
    NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NIM_API_KEY: str = ""                # Required in Phase 1; empty allowed in Phase 0
    NIM_MODEL_ENGINEERING: str = "nvidia/nemotron-4-340b-instruct"
    NIM_EMBEDDING_MODEL: str = "nvidia/nv-embedqa-e5-v5"
    NIM_INFERENCE_TEMPERATURE: float = 0.1   # Fixed for engineering queries; see CONTRIBUTING

    # ── NVIDIA PhysicsNeMo — Phase 2–3 ───────────────────────────────────
    PHYSICSNEMO_MODEL_STORE: str = "/opt/ewc/physicsnemo/models"
    PHYSICSNEMO_CACHE_DIR: str = "/opt/ewc/physicsnemo/cache"

    # ── NVIDIA Omniverse / OpenUSD — Phase 0 + Phase 3 ───────────────────
    OMNIVERSE_NUCLEUS_URL: str = "omniverse://localhost/Projects/EWCCompute"
    USD_EXCHANGE_SDK_PATH: str = "/opt/omniverse/exchange-sdk"
    OVPHYSX_ENDPOINT: str = "http://localhost:8010"   # Phase 3

    # ── Simulation Bridge — Phase 2 ───────────────────────────────────────
    LUMERICAL_API_URL: str = "http://localhost:8001"
    LUMERICAL_API_KEY: str = ""
    COMSOL_API_URL: str = "http://localhost:8002"
    COMSOL_API_KEY: str = ""
    ANSYS_API_URL: str = "http://localhost:8003"
    ANSYS_API_KEY: str = ""

    # ── RAG / vector search ───────────────────────────────────────────────
    VECTOR_SEARCH_INDEX: str = "ewc_engineering_corpus"

    # ── Observability ─────────────────────────────────────────────────────
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ── Derived helpers ───────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"

    @property
    def nim_available(self) -> bool:
        """True when NIM API key is configured — gates Phase 1 features."""
        return bool(self.NIM_API_KEY)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance — single read of environment at startup."""
    return Settings()


# Module-level singleton used throughout the application
settings: Settings = get_settings()
