---
name: travelpal-seaweedfs
description: Use when writing, modifying, or debugging any code that reads from or writes to SeaweedFS in the TravelPal pipeline — including boto3 client configuration, Parquet upload via SeaweedFSResource, public URL generation, bucket provisioning at startup, or moto mock setup for unit and integration tests. Also use when adding new ingest paths that must land Parquet in raw-flights or frontend-exports, when wiring DuckDB-WASM frontend access to SeaweedFS-hosted Parquet, or when diagnosing boto3 connection errors caused by missing endpoint_url.
---

# TravelPal SeaweedFS S3 Patterns

## Topology

| Service | Role | Port |
|---|---|---|
| `seaweedfs-master` | Metadata coordination | 9333 |
| `seaweedfs-volume` | Data storage | — |
| `seaweedfs-filer` | Filesystem interface | — |
| `seaweedfs-s3` | S3 API gateway | 8333 |

S3 endpoint:
- Dev: `http://localhost:8333`
- Docker-internal: `http://seaweedfs-s3:8333`

## SeaweedFSResource

`SeaweedFSResource` is a frozen Pydantic `BaseModel`. The boto3 client is built lazily via `cached_property` so Pydantic's frozen constraint is satisfied without `arbitrary_types_allowed` concerns on the field itself.

```python
import io
from functools import cached_property

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict


class SeaweedFSResource(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    @cached_property
    def _client(self):
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="us-east-1",  # SeaweedFS ignores region but boto3 requires it
        )

    def upload_parquet(self, table: pa.Table, bucket: str, key: str) -> None:
        buf = io.BytesIO()
        pq.write_table(table, buf)
        buf.seek(0)
        self._client.put_object(Bucket=bucket, Key=key, Body=buf.read())

    def get_public_url(self, bucket: str, key: str) -> str:
        return f"{self.endpoint}/{bucket}/{key}"
```

## Bucket Naming

| Bucket | Contents |
|---|---|
| `raw-flights` | Raw Parquet from OpenSky ingest |
| `frontend-exports` | Aggregated Parquet for DuckDB-WASM frontend |

Key pattern: `{airport_icao}/{filename}.parquet` — e.g. `KJFK/raw_flights.parquet`

Default values live in `PipelineConfig.raw_bucket` and `PipelineConfig.export_bucket`.

## moto Mock Fixture

`SeaweedFSResource` is a Pydantic model, so construct it with keyword args as normal:

```python
import boto3
from moto import mock_aws
import pytest


@pytest.fixture
def mock_s3():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="raw-flights")
        s3.create_bucket(Bucket="frontend-exports")
        yield SeaweedFSResource(
            endpoint="http://localhost:8333",
            access_key="test",
            secret_key="test",
        )
```

moto intercepts all boto3 calls globally within `mock_aws()` regardless of `endpoint_url`.

## DuckDB-WASM Frontend Access

Phase 0/1: direct public URL via `get_public_url(bucket, key)` — returns `{endpoint}/{bucket}/{key}`.

Frontend query: `SELECT * FROM read_parquet('http://...')`

## Rules

- `SeaweedFSResource` is a Pydantic `BaseModel(frozen=True)` — not a plain class.
- Always use `BytesIO` for in-memory Parquet — never write temp files to disk.
- `region_name="us-east-1"` is required by boto3 even though SeaweedFS ignores it.
- Credentials must come from `PipelineConfig`. Never log `access_key` or `secret_key`.
- Upload failures must propagate — do not silently catch `ClientError`.

## Common Mistake

```python
# WRONG: hits real AWS endpoints, not SeaweedFS
boto3.client("s3")

# CORRECT: always pass endpoint_url
boto3.client("s3", endpoint_url=cfg.seaweedfs_endpoint, ...)
```

Missing `endpoint_url` is the most common cause of `EndpointResolutionError` or unexpected `NoCredentialsError` in the TravelPal pipeline.
