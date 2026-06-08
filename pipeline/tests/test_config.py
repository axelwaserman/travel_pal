import pytest
from pydantic import ValidationError

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
    for key in [
        "AIRPORT_ICAO",
        "INGEST_START_DATE",
        "INGEST_END_DATE",
        "SEAWEEDFS_S3_ENDPOINT",
        "SEAWEEDFS_ACCESS_KEY",
        "SEAWEEDFS_SECRET_KEY",
        "NESSIE_ENDPOINT",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        PipelineConfig.from_env()


def test_config_is_frozen():
    config = PipelineConfig.model_validate(
        {
            "airport_icao": "KJFK",
            "ingest_start_date": "2024-01-01",
            "ingest_end_date": "2024-12-31",
            "SEAWEEDFS_S3_ENDPOINT": "http://localhost:8333",
            "seaweedfs_access_key": "admin",
            "seaweedfs_secret_key": "admin",
            "nessie_endpoint": "http://localhost:19120/api/v1",
        }
    )
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        config.airport_icao = "EGLL"  # type: ignore[misc]


def test_pipeline_config_has_bts_settings_with_defaults(monkeypatch):
    """PipelineConfig must expose bts_endpoint (default to BTS PREZIP URL),
    bts_fixture_file (None by default), and bts_cache_bucket ('bts-raw' default).
    """
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-01-08")
    monkeypatch.setenv("SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/iceberg/")

    cfg = PipelineConfig.from_env()

    assert cfg.bts_endpoint == "https://transtats.bts.gov/PREZIP"
    assert cfg.bts_fixture_file is None
    assert cfg.bts_cache_bucket == "bts-raw"


def test_pipeline_config_bts_fixture_file_overrides(monkeypatch, tmp_path):
    """When BTS_FIXTURE_FILE env var is set, the corresponding field is populated."""
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-01-08")
    monkeypatch.setenv("SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/iceberg/")
    fixture = tmp_path / "bts.zip"
    fixture.write_bytes(b"PK\x03\x04")  # ZIP magic
    monkeypatch.setenv("BTS_FIXTURE_FILE", str(fixture))

    cfg = PipelineConfig.from_env()

    assert cfg.bts_fixture_file == fixture


def test_pipeline_config_bts_fixture_file_empty_string_is_none(monkeypatch):
    """Empty BTS_FIXTURE_FILE (docker compose ${VAR:-} fallback) → None.

    Without this, an unset host var becomes "" inside the container, Pydantic
    coerces "" to Path("."), and BTSResource silently treats the working
    directory as the fixture ZIP — masking real-mode failures.
    """
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-01-08")
    monkeypatch.setenv("SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/iceberg/")
    monkeypatch.setenv("BTS_FIXTURE_FILE", "")

    cfg = PipelineConfig.from_env()

    assert cfg.bts_fixture_file is None
