from unittest.mock import AsyncMock, MagicMock

import pyarrow as pa

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


def _make_config() -> PipelineConfig:
    return PipelineConfig.model_validate(
        {
            "airport_icao": "KJFK",
            "ingest_start_date": "2024-01-01",
            "ingest_end_date": "2024-01-08",
            "SEAWEEDFS_S3_ENDPOINT": "http://localhost:8333",
            "seaweedfs_access_key": "admin",
            "seaweedfs_secret_key": "admin",
            "nessie_endpoint": "http://localhost:19120/api/v1",
        }
    )


def test_raw_flights_asset_creates_table_and_appends():
    config = _make_config()
    mock_opensky = MagicMock()
    mock_opensky.fetch_departures = AsyncMock(return_value=SAMPLE_TABLE)
    mock_opensky.fetch_arrivals = AsyncMock(return_value=SAMPLE_TABLE)

    mock_nessie = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.table_exists.return_value = False
    mock_nessie.catalog = mock_catalog

    combined_expected = pa.concat_tables([SAMPLE_TABLE, SAMPLE_TABLE])

    result = raw_flights(
        pipeline_config=config,
        opensky=mock_opensky,
        nessie=mock_nessie,
    )

    assert mock_catalog.table_exists.called
    mock_catalog.create_namespace_if_not_exists.assert_called_once_with("flights")
    mock_catalog.create_table.assert_called_once()
    assert result.num_rows == 2  # departures row + arrivals row

    mock_catalog.load_table.assert_called_once_with("flights.raw_flights")
    mock_catalog.load_table.return_value.append.assert_called_once()
    appended_table = mock_catalog.load_table.return_value.append.call_args.args[0]
    assert appended_table.num_rows == combined_expected.num_rows


def test_raw_flights_returns_empty_table_when_no_data():
    config = _make_config()
    empty = pa.table(
        {
            "icao24": pa.array([], type=pa.string()),
            "callsign": pa.array([], type=pa.string()),
            "first_seen": pa.array([], type=pa.int64()),
            "last_seen": pa.array([], type=pa.int64()),
            "est_departure_airport": pa.array([], type=pa.string()),
            "est_arrival_airport": pa.array([], type=pa.string()),
        }
    )
    mock_opensky = MagicMock()
    mock_opensky.fetch_departures = AsyncMock(return_value=empty)
    mock_opensky.fetch_arrivals = AsyncMock(return_value=empty)
    mock_nessie = MagicMock()
    mock_catalog = MagicMock()
    mock_nessie.catalog = mock_catalog

    result = raw_flights(
        pipeline_config=config,
        opensky=mock_opensky,
        nessie=mock_nessie,
    )

    assert isinstance(result, pa.Table)
    assert result.num_rows == 0
    mock_catalog.table_exists.assert_not_called()
    mock_catalog.create_table.assert_not_called()
    mock_catalog.load_table.assert_not_called()


def test_raw_flights_appends_to_existing_table_without_create():
    config = _make_config()
    mock_opensky = MagicMock()
    mock_opensky.fetch_departures = AsyncMock(return_value=SAMPLE_TABLE)
    mock_opensky.fetch_arrivals = AsyncMock(return_value=SAMPLE_TABLE)

    mock_nessie = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.table_exists.return_value = True
    mock_nessie.catalog = mock_catalog

    result = raw_flights(
        pipeline_config=config,
        opensky=mock_opensky,
        nessie=mock_nessie,
    )

    assert result.num_rows == 2

    mock_catalog.create_namespace_if_not_exists.assert_not_called()
    mock_catalog.create_table.assert_not_called()

    mock_catalog.load_table.assert_called_once_with("flights.raw_flights")
    mock_catalog.load_table.return_value.append.assert_called_once()
