from pydantic import AliasChoices, ConfigDict, Field
from pydantic_settings import BaseSettings


class PipelineConfig(BaseSettings):
    airport_icao: str
    ingest_start_date: str
    ingest_end_date: str
    # Accept both SEAWEEDFS_ENDPOINT and legacy SEAWEEDFS_S3_ENDPOINT
    seaweedfs_endpoint: str = Field(
        validation_alias=AliasChoices("SEAWEEDFS_ENDPOINT", "SEAWEEDFS_S3_ENDPOINT")
    )
    seaweedfs_access_key: str
    seaweedfs_secret_key: str
    nessie_endpoint: str
    raw_bucket: str = "raw-flights"
    export_bucket: str = "frontend-exports"
    opensky_username: str = ""
    opensky_password: str = ""

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls()
