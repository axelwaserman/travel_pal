import pyarrow as pa
from unittest.mock import patch, MagicMock
from pipeline.resources.seaweedfs import SeaweedFSResource
from pipeline.resources.nessie import NessieResource


def test_seaweedfs_upload_parquet(tmp_path):
    resource = SeaweedFSResource(
        endpoint="http://localhost:8333",
        access_key="admin",
        secret_key="admin",
    )
    table = pa.table({"icao24": ["abc"], "callsign": ["AA1"]})

    with patch("pipeline.resources.seaweedfs.boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        resource.upload_parquet(table, bucket="raw-flights", key="test/data.parquet")

    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "raw-flights"
    assert call_kwargs["Key"] == "test/data.parquet"


def test_nessie_resource_init():
    resource = NessieResource(endpoint="http://localhost:19120/api/v1")
    assert resource.endpoint == "http://localhost:19120/api/v1"
