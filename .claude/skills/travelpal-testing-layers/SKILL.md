---
name: travelpal-testing-layers
description: Use when writing, fixing, or reviewing tests for the TravelPal pipeline. Use when adding a new Dagster asset, dbt model, adapter, or export function and tests must be placed in the correct layer. Use when a test incorrectly performs real I/O in a unit test, or incorrectly mocks DuckDB in an integration test. Use when coverage is below 80% and the gap must be closed across all three layers.
---

# TravelPal Testing Layers

The TravelPal pipeline enforces a strict three-layer test strategy. All three layers are required. Minimum 80% coverage across the pipeline.

## Directory Layout

```
pipeline/tests/
├── test_config.py
├── test_opensky.py
├── test_resources.py
└── test_asset_raw_flights.py
```

Current tests are flat. As the pipeline grows, migrate to subdirectories:

```
pipeline/tests/
├── unit/           — fast, no I/O, mock all external deps
├── integration/    — real DuckDB, moto S3, no network
└── e2e/            — Dagster materialize, full pipeline
```

## Layer 1 — Unit Tests

**Rule: zero real I/O. Mock all external dependencies.**

Mock targets: `SeaweedFSResource`, `NessieResource`, `OpenSkyAdapter`.

`fetch_departures` and `fetch_arrivals` are `async` — use `AsyncMock`, not `MagicMock.return_value`:

```python
import pyarrow as pa
from unittest.mock import AsyncMock, MagicMock
import pytest

SAMPLE_TABLE = pa.table({
    "icao24": ["a1b2c3"],
    "callsign": ["AA100"],
    "first_seen": [1704067200],
    "last_seen": [1704074400],
    "est_departure_airport": ["KJFK"],
    "est_arrival_airport": ["KLAX"],
})

def test_raw_flights_uploads_parquet():
    config = PipelineConfig(
        airport_icao="KJFK",
        ingest_start_date="2024-01-01",
        ingest_end_date="2024-01-08",
        seaweedfs_endpoint="http://localhost:8333",
        seaweedfs_access_key="admin",
        seaweedfs_secret_key="admin",
        nessie_endpoint="http://localhost:19120/api/v1",
    )
    opensky = MagicMock(spec=OpenSkyAdapter)
    opensky.fetch_departures = AsyncMock(return_value=SAMPLE_TABLE)
    opensky.fetch_arrivals = AsyncMock(return_value=SAMPLE_TABLE)
    seaweedfs = MagicMock(spec=SeaweedFSResource)
    nessie = MagicMock(spec=NessieResource)
    mock_catalog = MagicMock()
    nessie.catalog = mock_catalog

    result = raw_flights(
        pipeline_config=config,
        opensky=opensky,
        seaweedfs=seaweedfs,
        nessie=nessie,
    )
    seaweedfs.upload_parquet.assert_called_once()
    assert result.num_rows == 2
```

For testing `OpenSkyAdapter` internals, mock `_fetch_chunk` or `_client` directly:

```python
@pytest.mark.asyncio
async def test_fetch_departures_returns_arrow_table():
    adapter = OpenSkyAdapter()
    with patch.object(adapter, "_fetch_chunk", new=AsyncMock(
        return_value=[OpenSkyFlight.model_validate(SAMPLE_RESPONSE[0])]
    )):
        table = await adapter.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    assert isinstance(table, pa.Table)
    assert table.num_rows == 1
```

## Layer 2 — Integration Tests

**Rule: real DuckDB, `moto` for S3/SeaweedFS, no network.**

```python
import duckdb
from moto import mock_aws
import boto3
import subprocess

@mock_aws
def test_dbt_models_produce_agg_tables(tmp_path):
    # Seed real DuckDB with fixture data
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    con.execute("CREATE TABLE stg_flights AS SELECT ...")
    con.close()

    # Run dbt against real DuckDB — profiles.yml must point at tmp_path/test.duckdb
    result = subprocess.run(
        ["dbt", "run", "--project-dir", "transforms", "--profiles-dir", str(tmp_path)],
        capture_output=True,
    )
    assert result.returncode == 0

    # Verify output
    con = duckdb.connect(str(tmp_path / "test.duckdb"), read_only=True)
    rows = con.execute("SELECT * FROM agg_route_timeliness").fetchall()
    assert len(rows) > 0
```

The `profiles.yml` fixture must set `path` to `str(tmp_path / "test.duckdb")`.

## Layer 3 — E2E Tests

**Rule: Dagster `materialize()` with real execution graph. No production SeaweedFS or OpenSky.**

```python
from dagster import materialize

def test_full_pipeline_materializes(mock_opensky_server):
    result = materialize(
        [raw_flights, transformed_flights, frontend_exports],
        resources={
            "pipeline_config": ResourceDefinition.hardcoded_resource(test_config),
            "opensky": ResourceDefinition.hardcoded_resource(
                OpenSkyAdapter(username="", password="")
            ),
            ...
        },
    )
    assert result.success
```

## Invariants

- `PipelineConfig` in tests always uses explicit constructor arguments — never `PipelineConfig.from_env()`.
- When required env vars are absent, the expected exception is `pydantic.ValidationError`, not `KeyError`.
- `fetch_departures` and `fetch_arrivals` are `async` — always use `AsyncMock`.
- Never connect to production SeaweedFS or the live OpenSky API in CI.
- Unit tests must not instantiate a real `duckdb.Connection` against a file path.
- Integration tests must not `patch` DuckDB — use a real in-process connection against `tmp_path`.
- E2E tests must use Dagster's `materialize()` — do not call asset functions directly.
