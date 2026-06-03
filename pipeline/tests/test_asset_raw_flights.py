import pytest
import pyarrow as pa
from unittest.mock import AsyncMock, MagicMock
from pipeline.assets.raw_flights import raw_flights
from pipeline.config import PipelineConfig


SAMPLE_TABLE = pa.table({
    "icao24": ["a1b2c3"],
    "callsign": ["AA100"],
    "first_seen": [1704067200],
    "last_seen": [1704074400],
    "est_departure_airport": ["KJFK"],
    "est_arrival_airport": ["KLAX"],
})


def _make_config() -> PipelineConfig:
    return PipelineConfig(
        airport_icao="KJFK",
        ingest_start_date="2024-01-01",
        ingest_end_date="2024-01-08",
        seaweedfs_endpoint="http://localhost:8333",
        seaweedfs_access_key="admin",
        seaweedfs_secret_key="admin",
        nessie_endpoint="http://localhost:19120/api/v1",
    )


def test_raw_flights_asset_uploads_and_registers():
    config = _make_config()
    mock_opensky = MagicMock()
    mock_opensky.fetch_departures = AsyncMock(return_value=SAMPLE_TABLE)
    mock_opensky.fetch_arrivals = AsyncMock(return_value=SAMPLE_TABLE)

    mock_seaweedfs = MagicMock()
    mock_nessie = MagicMock()
    mock_catalog = MagicMock()
    mock_nessie.catalog = mock_catalog

    result = raw_flights(
        pipeline_config=config,
        opensky=mock_opensky,
        seaweedfs=mock_seaweedfs,
        nessie=mock_nessie,
    )

    mock_seaweedfs.upload_parquet.assert_called_once()
    upload_key = mock_seaweedfs.upload_parquet.call_args.kwargs["key"]
    assert upload_key == "KJFK/raw_flights.parquet"
    assert mock_catalog.table_exists.called
    assert result.num_rows == 2  # departures row + arrivals row


def test_raw_flights_returns_empty_table_when_no_data():
    config = _make_config()
    empty = pa.table({
        "icao24": pa.array([], type=pa.string()),
        "callsign": pa.array([], type=pa.string()),
        "first_seen": pa.array([], type=pa.int64()),
        "last_seen": pa.array([], type=pa.int64()),
        "est_departure_airport": pa.array([], type=pa.string()),
        "est_arrival_airport": pa.array([], type=pa.string()),
    })
    mock_opensky = MagicMock()
    mock_opensky.fetch_departures = AsyncMock(return_value=empty)
    mock_opensky.fetch_arrivals = AsyncMock(return_value=empty)
    mock_seaweedfs = MagicMock()
    mock_nessie = MagicMock()
    mock_nessie.catalog = MagicMock()

    result = raw_flights(
        pipeline_config=config,
        opensky=mock_opensky,
        seaweedfs=mock_seaweedfs,
        nessie=mock_nessie,
    )

    assert isinstance(result, pa.Table)
    assert result.num_rows == 0
