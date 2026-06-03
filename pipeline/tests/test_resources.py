import pyarrow as pa
from unittest.mock import patch, MagicMock
from pipeline.resources.seaweedfs import SeaweedFSResource
from pipeline.resources.nessie import NessieResource


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
    resource = NessieResource(endpoint="http://localhost:19120/api/v1")
    assert resource.endpoint == "http://localhost:19120/api/v1"
    assert resource.model_config.get("frozen") is True
