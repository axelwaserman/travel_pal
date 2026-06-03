"""Integration tests for PyIceberg append + read path.

Marked @pytest.mark.integration. Uses a SQL (SQLite) catalog backed by a local
filesystem warehouse (``file://``).

Note on storage: PyIceberg's PyArrow S3FileSystem uses the Arrow C++ S3 client,
which performs multipart uploads and cannot be intercepted by moto's boto3-layer
patching.  The local filesystem warehouse exercises the same Iceberg catalog,
schema validation, append, and scan code-paths without requiring docker or a live
S3-compatible endpoint.  S3 storage is covered at the E2E layer (live SeaweedFS).
"""
from pathlib import Path

import pyarrow as pa
import pytest
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType


SAMPLE = pa.table(
    {
        "icao24": ["a1b2c3"],
        "callsign": ["AA100"],
        "first_seen": [1704067200],
        "last_seen": [1704074400],
        "est_departure_airport": ["KJFK"],
        "est_arrival_airport": ["KLAX"],
    }
)

SCHEMA = Schema(
    NestedField(1, "icao24", StringType(), required=False),
    NestedField(2, "callsign", StringType(), required=False),
    NestedField(3, "first_seen", LongType(), required=False),
    NestedField(4, "last_seen", LongType(), required=False),
    NestedField(5, "est_departure_airport", StringType(), required=False),
    NestedField(6, "est_arrival_airport", StringType(), required=False),
)


@pytest.mark.integration
def test_iceberg_append_and_scan_round_trip(tmp_path: Path) -> None:
    """Create an Iceberg table on a SQL catalog with a local warehouse, append data, read it back."""
    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()

    catalog = SqlCatalog(
        "default",
        **{
            "uri": f"sqlite:///{tmp_path / 'catalog.db'}",
            "warehouse": f"file://{warehouse}",
        },
    )

    catalog.create_namespace("flights")
    catalog.create_table("flights.raw_flights", schema=SCHEMA)
    table = catalog.load_table("flights.raw_flights")
    table.append(SAMPLE)

    # Re-load and scan to exercise the full read path.
    table = catalog.load_table("flights.raw_flights")
    scanned = table.scan().to_arrow()

    assert scanned.num_rows == 1
    assert scanned.column("callsign").to_pylist() == ["AA100"]


@pytest.mark.integration
def test_iceberg_append_multiple_batches(tmp_path: Path) -> None:
    """Appending two separate batches should accumulate rows correctly."""
    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()

    catalog = SqlCatalog(
        "default",
        **{
            "uri": f"sqlite:///{tmp_path / 'catalog.db'}",
            "warehouse": f"file://{warehouse}",
        },
    )

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

    catalog.create_namespace("flights")
    catalog.create_table("flights.raw_flights", schema=SCHEMA)
    table = catalog.load_table("flights.raw_flights")
    table.append(SAMPLE)
    table.append(second_batch)

    table = catalog.load_table("flights.raw_flights")
    scanned = table.scan().to_arrow()

    assert scanned.num_rows == 2
    assert set(scanned.column("callsign").to_pylist()) == {"AA100", "BA200"}
