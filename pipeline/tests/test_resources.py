import pytest
import pyarrow as pa
from unittest.mock import patch, MagicMock
from dagster import ConfigurableResource
from pipeline.resources.seaweedfs import SeaweedFSResource
from pipeline.resources.nessie import NessieResource
from pydantic import ValidationError


def _make_seaweedfs() -> SeaweedFSResource:
    return SeaweedFSResource(
        endpoint="http://localhost:8333",
        access_key="admin",
        secret_key="admin",
    )


def test_seaweedfs_upload_parquet():
    resource = _make_seaweedfs()
    table = pa.table({"icao24": ["abc"], "callsign": ["AA1"]})

    with patch("pipeline.resources.seaweedfs.boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        resource.upload_parquet(table, bucket="raw-flights", key="test/data.parquet")

    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "raw-flights"
    assert call_kwargs["Key"] == "test/data.parquet"
    assert call_kwargs["Body"]  # non-empty bytes


def test_seaweedfs_is_pydantic_model():
    resource = _make_seaweedfs()
    assert resource.endpoint == "http://localhost:8333"
    assert resource.model_config.get("frozen") is True


def test_seaweedfs_get_public_url():
    resource = _make_seaweedfs()
    url = resource.get_public_url("frontend-exports", "KJFK/route_timeliness.parquet")
    assert url == "http://localhost:8333/frontend-exports/KJFK/route_timeliness.parquet"


def test_nessie_resource_is_pydantic_model():
    resource = NessieResource(
        endpoint="http://localhost:19120/iceberg/",
        s3_endpoint="http://localhost:8333",
        s3_access_key="admin",
        s3_secret_key="admin",
    )
    assert resource.endpoint == "http://localhost:19120/iceberg/"
    assert resource.warehouse == "warehouse"
    assert resource.s3_region == "us-east-1"
    assert resource.model_config.get("frozen") is True


def test_opensky_resource_is_configurable_resource():
    from pipeline.resources.opensky import OpenSkyResource
    resource = OpenSkyResource(client_id="id", client_secret="secret")
    assert resource.client_id == "id"
    assert resource.client_secret == "secret"
    assert isinstance(resource, ConfigurableResource)


def test_opensky_resource_defaults_to_empty_credentials():
    from pipeline.resources.opensky import OpenSkyResource
    resource = OpenSkyResource()
    assert resource.client_id == ""
    assert resource.client_secret == ""


# ---------------------------------------------------------------------------
# _resources_or_empty prod-guard tests
# ---------------------------------------------------------------------------

def test_resources_or_empty_returns_empty_dict_when_env_vars_missing(monkeypatch):
    """Without env vars present (and no DAGSTER_ENV=prod), should return {}."""
    monkeypatch.delenv("DAGSTER_ENV", raising=False)
    # Ensure none of the required config env vars are set
    for var in (
        "OPENSKY_CLIENT_ID", "OPENSKY_CLIENT_SECRET",
        "SEAWEEDFS_S3_ENDPOINT", "SEAWEEDFS_ACCESS_KEY", "SEAWEEDFS_SECRET_KEY",
        "NESSIE_ENDPOINT", "AIRPORT_ICAO", "INGEST_START_DATE", "INGEST_END_DATE",
    ):
        monkeypatch.delenv(var, raising=False)

    from pipeline import _resources_or_empty
    result = _resources_or_empty()
    assert result == {}


def test_resources_or_empty_raises_in_prod_when_env_vars_missing(monkeypatch):
    """With DAGSTER_ENV=prod set, missing config must raise instead of silently returning {}."""
    monkeypatch.setenv("DAGSTER_ENV", "prod")
    for var in (
        "OPENSKY_CLIENT_ID", "OPENSKY_CLIENT_SECRET",
        "SEAWEEDFS_S3_ENDPOINT", "SEAWEEDFS_ACCESS_KEY", "SEAWEEDFS_SECRET_KEY",
        "NESSIE_ENDPOINT", "AIRPORT_ICAO", "INGEST_START_DATE", "INGEST_END_DATE",
    ):
        monkeypatch.delenv(var, raising=False)

    from pipeline import _resources_or_empty
    with pytest.raises((KeyError, ValidationError)):
        _resources_or_empty()
