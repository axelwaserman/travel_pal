"""Integration tests for PyIceberg append + read path via Nessie REST + SeaweedFS S3.

Marked @pytest.mark.integration.

These tests exercise the *real* catalog and storage stack:
  - PyIceberg RestCatalog → Nessie Iceberg REST Catalog (http://localhost:19120/iceberg/)
  - Apache Iceberg data files written to SeaweedFS S3 (http://localhost:8333)

Tests are skipped automatically when the Docker daemon is not reachable.
Infrastructure is started (and torn down) by fixtures in
``pipeline/tests/integration/conftest.py``.

Iceberg schema mirrors the production ``raw_flights`` table schema used in
``pipeline/assets/raw_flights.py``.
"""
import uuid

import pyarrow as pa
import pytest

from tests.integration._docker import DOCKER_AVAILABLE
from tests.integration._iceberg import (
    RAW_FLIGHTS_SCHEMA,
    InfraEndpoints,
    make_catalog,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE: pa.Table = pa.table(
    {
        "icao24": ["a1b2c3"],
        "callsign": ["AA100"],
        "first_seen": [1704067200],
        "last_seen": [1704074400],
        "est_departure_airport": ["KJFK"],
        "est_arrival_airport": ["KLAX"],
    }
)

# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------

_SKIP_REASON = "Docker daemon is not reachable — skipping integration tests."
skip_if_no_docker = pytest.mark.skipif(not DOCKER_AVAILABLE, reason=_SKIP_REASON)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@skip_if_no_docker
def test_iceberg_append_and_scan_round_trip(
    infra_endpoints: InfraEndpoints,
    seaweedfs_init: None,
) -> None:
    """Create an Iceberg table on the Nessie REST catalog backed by SeaweedFS S3,
    append sample data, read it back, and assert the row count and a column value.
    """
    catalog = make_catalog(infra_endpoints)

    # Use a unique namespace per test run so parallel/repeated runs don't clash.
    namespace = f"flights_test_{uuid.uuid4().hex[:8]}"
    catalog.create_namespace(namespace)
    table_id = f"{namespace}.raw_flights"

    catalog.create_table(table_id, schema=RAW_FLIGHTS_SCHEMA)
    table = catalog.load_table(table_id)
    table.append(SAMPLE)

    # Re-load to exercise the full Nessie → S3 read path.
    table = catalog.load_table(table_id)
    scanned: pa.Table = table.scan().to_arrow()

    assert scanned.num_rows == 1
    assert scanned.column("callsign").to_pylist() == ["AA100"]


@pytest.mark.integration
@skip_if_no_docker
def test_iceberg_append_multiple_batches(
    infra_endpoints: InfraEndpoints,
    seaweedfs_init: None,
) -> None:
    """Appending two separate batches should accumulate rows correctly."""
    catalog = make_catalog(infra_endpoints)

    namespace = f"flights_test_{uuid.uuid4().hex[:8]}"
    catalog.create_namespace(namespace)
    table_id = f"{namespace}.raw_flights"

    second_batch = pa.table(
        {
            "icao24": ["d4e5f6"],
            "callsign": ["BA200"],
            "first_seen": [1704070800],
            "last_seen": [1704078000],
            "est_departure_airport": ["EGLL"],
            "est_arrival_airport": ["KJFK"],
        }
    )

    catalog.create_table(table_id, schema=RAW_FLIGHTS_SCHEMA)
    table = catalog.load_table(table_id)
    table.append(SAMPLE)
    table.append(second_batch)

    table = catalog.load_table(table_id)
    scanned: pa.Table = table.scan().to_arrow()

    assert scanned.num_rows == 2
    assert set(scanned.column("callsign").to_pylist()) == {"AA100", "BA200"}
