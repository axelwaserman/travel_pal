import pytest


@pytest.mark.unit
def test_bts_on_time_asset_registered():
    """The bts_on_time asset must be in the Definitions assets list."""
    from pipeline import defs

    asset_keys = {a.key.to_user_string() for a in defs.assets}  # type: ignore[attr-defined]
    assert "bts_on_time" in asset_keys, f"bts_on_time missing from Definitions; have {asset_keys}"


@pytest.mark.unit
def test_bts_resource_registered_when_env_present(monkeypatch):
    """When env vars are present, defs.resources contains a 'bts' resource."""
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-01-08")
    monkeypatch.setenv("SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/iceberg/")

    # Reload module so resources rebuild against fresh env.
    import importlib

    import pipeline

    importlib.reload(pipeline)

    assert "bts" in pipeline.defs.resources  # type: ignore[attr-defined]
