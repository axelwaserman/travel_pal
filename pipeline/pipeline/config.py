from pydantic import Field
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

    model_config = SettingsConfigDict(frozen=True, case_sensitive=False)

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls()  # ty: ignore[missing-argument]  # BaseSettings reads env
