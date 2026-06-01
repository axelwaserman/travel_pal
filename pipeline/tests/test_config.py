import os
import pytest
from pipeline.config import PipelineConfig


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-12-31")
    monkeypatch.setenv("SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/api/v1")

    config = PipelineConfig.from_env()

    assert config.airport_icao == "KJFK"
    assert config.raw_bucket == "raw-flights"
    assert config.export_bucket == "frontend-exports"


def test_config_missing_env_raises(monkeypatch):
    monkeypatch.delenv("AIRPORT_ICAO", raising=False)
    with pytest.raises(KeyError):
        PipelineConfig.from_env()
