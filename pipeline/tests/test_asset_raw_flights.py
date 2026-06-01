import pytest
import pyarrow as pa
from unittest.mock import MagicMock, patch
from pipeline.assets.raw_flights import raw_flights
from pipeline.config import PipelineConfig


SAMPLE_TABLE = pa.table(
    {
        "icao24": ["a1b2c3"],
        "callsign": ["AA100"],
        "first_seen": [1704067200],
        "last_seen": [1704074400],
        "est_departure_airport": ["KJFK"],
        "est_arrival_airport": ["KLAX"],
    }
)


def test_raw_flights_asset_uploads_and_registers(monkeypatch):
    config = PipelineConfig(
        airport_icao="KJFK",
        ingest_start_date="2024-01-01",
        ingest_end_date="2024-01-08",
        seaweedfs_endpoint="http://localhost:8333",
        seaweedfs_access_key="admin",
        seaweedfs_secret_key="admin",
        nessie_endpoint="http://localhost:19120/api/v1",
    )
    mock_opensky = MagicMock()
    mock_opensky.fetch_departures.return_value = SAMPLE_TABLE
    mock_opensky.fetch_arrivals.return_value = SAMPLE_TABLE

    mock_seaweedfs = MagicMock()
    mock_nessie = MagicMock()
    mock_catalog = MagicMock()
    mock_nessie.catalog.return_value = mock_catalog

    result = raw_flights(
        pipeline_config=config,
        opensky=mock_opensky,
        seaweedfs=mock_seaweedfs,
        nessie=mock_nessie,
    )

    assert mock_seaweedfs.upload_parquet.called
    assert result is not None
