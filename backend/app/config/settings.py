"""Application configuration.

Every tunable value in INTELORA is read from the environment through this
module. Nothing elsewhere in the backend may read ``os.environ`` directly, so
that the full configuration surface is visible in one place and secrets never
appear in source.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated view of the process environment."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime -------------------------------------------------------------
    intelora_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    app_name: str = Field(default="INTELORA")
    app_description: str = Field(
        default="Enterprise AIOT Intelligence Platform — Telemetry, "
        "Intelligence and Business Intelligence layers."
    )
    app_version: str = Field(default="1.0.0")

    # --- Database ------------------------------------------------------------
    postgres_user: str = Field(default="intelora")
    postgres_password: str = Field(default="intelora")
    postgres_db: str = Field(default="intelora")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)

    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=20, ge=0)
    db_echo: bool = Field(default=False)

    # --- API -----------------------------------------------------------------
    api_v1_prefix: str = Field(default="/api/v1")
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:4173,http://localhost:8080"
    )

    # --- Digital Twin Engine -------------------------------------------------
    twin_enabled: bool = Field(default=True)
    twin_interval_seconds: float = Field(default=1.0, gt=0)
    twin_laptop_chargers: int = Field(default=50, ge=0)
    twin_mobile_chargers: int = Field(default=50, ge=0)
    twin_air_conditioners: int = Field(default=20, ge=0)
    twin_seed: int | None = Field(default=20260801)

    # How many telemetry rows to accumulate before a single bulk insert. The
    # engine ticks at 1 Hz across the whole fleet, so batching keeps write
    # amplification low without delaying the live broadcast.
    twin_write_batch: int = Field(default=120, ge=1)

    # --- Intelligence --------------------------------------------------------
    intelligence_interval_seconds: float = Field(default=15.0, gt=0)

    # Rolling window, in minutes, that the intelligence layers analyse.
    intelligence_window_minutes: int = Field(default=30, ge=1)

    # --- Business Intelligence -----------------------------------------------
    # Blended commercial electricity tariff used to convert energy into cost.
    energy_tariff_per_kwh: float = Field(default=0.14, ge=0)
    currency_code: str = Field(default="USD")

    # --- Time-series storage -------------------------------------------------
    # At 120 devices and 1 Hz the platform writes ~10.4 million rows a day, so
    # raw retention alone is not a viable read path for anything beyond a few
    # hours. Continuous aggregates and compression are what make "last 30 days"
    # answerable at all; these switches exist so the behaviour can be disabled
    # on a plain PostgreSQL instance without TimescaleDB.
    timescale_compression_enabled: bool = Field(default=True)
    timescale_continuous_aggregates_enabled: bool = Field(default=True)

    #: Chunk width for the telemetry hypertable. Sized so a chunk stays small
    #: enough to keep recent data in memory at the configured write rate.
    timescale_chunk_interval_hours: int = Field(default=2, ge=1)

    #: Age at which a chunk is compressed. Must exceed the window the
    #: intelligence layers scan, so hot data is never decompressed on read.
    timescale_compress_after_hours: int = Field(default=6, ge=1)

    @field_validator("twin_seed", mode="before")
    @classmethod
    def _empty_seed_is_none(cls, value: object) -> object:
        """Treat an empty environment variable as "no seed"."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        return value.upper()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy DSN."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, parsed from the comma-separated variable."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.intelora_env.lower() in {"production", "prod"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so that configuration is parsed and validated exactly once. FastAPI
    dependencies and background tasks share the same instance.
    """
    return Settings()


settings = get_settings()
