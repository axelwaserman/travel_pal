from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineConfig(BaseSettings):
    airport_icao: str
    ingest_start_date: str
    ingest_end_date: str
    seaweedfs_endpoint: str = Field(validation_alias="SEAWEEDFS_S3_ENDPOINT")
    seaweedfs_access_key: str
    seaweedfs_secret_key: str
    nessie_endpoint: str
    raw_bucket: str = "raw-flights"
    export_bucket: str = "frontend-exports"
    opensky_client_id: str = ""
    opensky_client_secret: str = ""

    # Phase 1 — BTS On-Time Performance ingestion
    bts_endpoint: str = "https://transtats.bts.gov/PREZIP"
    bts_fixture_file: Path | None = None
    bts_cache_bucket: str = "bts-raw"

    model_config = SettingsConfigDict(frozen=True, case_sensitive=False)

    @field_validator("bts_fixture_file", mode="before")
    @classmethod
    def _empty_str_is_none(cls, v: object) -> object:
        # docker compose interpolates ${BTS_FIXTURE_FILE:-} to an empty string
        # when the host var is unset. Pydantic would then coerce "" to Path("."),
        # which silently activates fixture mode pointing at the working dir.
        # Treat empty/whitespace as "not set".
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls()  # ty: ignore[missing-argument]  # BaseSettings reads env
