"""Integration tests for the SeaweedFS / S3 round-trip path.

Marked @pytest.mark.integration. Uses moto[s3] so no docker stack is required.
moto patches boto3 at the client layer, intercepting calls regardless of
endpoint_url.  SeaweedFSResource creates its boto3 client via a cached_property;
each test instantiates a fresh resource so there is no cross-test cache pollution.
"""
import io

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from moto import mock_aws

from pipeline.resources.seaweedfs import SeaweedFSResource


SAMPLE = pa.table(
    {
        "icao24": ["a1b2c3", "d4e5f6"],
        "callsign": ["AA100", "BA200"],
        "first_seen": [1704067200, 1704070800],
        "last_seen": [1704074400, 1704078000],
        "est_departure_airport": ["KJFK", "EGLL"],
        "est_arrival_airport": ["KLAX", "KJFK"],
    }
)


@pytest.mark.integration
@mock_aws
def test_seaweedfs_upload_and_download_round_trip() -> None:
    """Upload a parquet file via SeaweedFSResource, download it via boto3, verify rows match."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="raw-flights")

    resource = SeaweedFSResource(
        endpoint="https://s3.us-east-1.amazonaws.com",
        access_key="testing",
        secret_key="testing",
    )

    resource.upload_parquet(SAMPLE, bucket="raw-flights", key="KJFK/raw_flights.parquet")

    obj = s3.get_object(Bucket="raw-flights", Key="KJFK/raw_flights.parquet")
    body = obj["Body"].read()
    table = pq.read_table(io.BytesIO(body))

    assert table.num_rows == 2
    assert set(table.column_names) == set(SAMPLE.column_names)
    assert table.column("callsign").to_pylist() == ["AA100", "BA200"]


@pytest.mark.integration
@mock_aws
def test_seaweedfs_overwrite_existing_key() -> None:
    """Uploading to an existing key should overwrite cleanly (idempotent re-runs)."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="raw-flights")

    resource = SeaweedFSResource(
        endpoint="https://s3.us-east-1.amazonaws.com",
        access_key="testing",
        secret_key="testing",
    )
    key = "KJFK/raw_flights.parquet"

    resource.upload_parquet(SAMPLE, bucket="raw-flights", key=key)

    smaller = SAMPLE.slice(0, 1)
    resource.upload_parquet(smaller, bucket="raw-flights", key=key)

    obj = s3.get_object(Bucket="raw-flights", Key=key)
    table = pq.read_table(io.BytesIO(obj["Body"].read()))
    assert table.num_rows == 1
