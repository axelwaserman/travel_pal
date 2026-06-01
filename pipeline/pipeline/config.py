from dataclasses import dataclass
import os


@dataclass(frozen=True)
class PipelineConfig:
    airport_icao: str
    ingest_start_date: str
    ingest_end_date: str
    seaweedfs_endpoint: str
    seaweedfs_access_key: str
    seaweedfs_secret_key: str
    nessie_endpoint: str
    raw_bucket: str = "raw-flights"
    export_bucket: str = "frontend-exports"

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls(
            airport_icao=os.environ["AIRPORT_ICAO"],
            ingest_start_date=os.environ["INGEST_START_DATE"],
            ingest_end_date=os.environ["INGEST_END_DATE"],
            seaweedfs_endpoint=os.environ["SEAWEEDFS_S3_ENDPOINT"],
            seaweedfs_access_key=os.environ["SEAWEEDFS_ACCESS_KEY"],
            seaweedfs_secret_key=os.environ["SEAWEEDFS_SECRET_KEY"],
            nessie_endpoint=os.environ["NESSIE_ENDPOINT"],
        )
