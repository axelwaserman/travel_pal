import pytest
from pydantic import ValidationError
from pipeline.config import PipelineConfig


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-12-31")
    monkeypatch.setenv("SEAWEEDFS_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/api/v1")

    config = PipelineConfig.from_env()

    assert config.airport_icao == "KJFK"
    assert config.raw_bucket == "raw-flights"
    assert config.export_bucket == "frontend-exports"


def test_config_missing_env_raises(monkeypatch):
    for key in [
        "AIRPORT_ICAO", "INGEST_START_DATE", "INGEST_END_DATE",
        "SEAWEEDFS_ENDPOINT", "SEAWEEDFS_ACCESS_KEY", "SEAWEEDFS_SECRET_KEY",
        "NESSIE_ENDPOINT",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        PipelineConfig.from_env()


def test_config_is_frozen():
    config = PipelineConfig(
        airport_icao="KJFK",
        ingest_start_date="2024-01-01",
        ingest_end_date="2024-12-31",
        seaweedfs_endpoint="http://localhost:8333",
        seaweedfs_access_key="admin",
        seaweedfs_secret_key="admin",
        nessie_endpoint="http://localhost:19120/api/v1",
    )
    with pytest.raises(Exception):
        config.airport_icao = "EGLL"  # type: ignore[misc]
