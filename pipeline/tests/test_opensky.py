import pyarrow as pa
from unittest.mock import patch, MagicMock
from pipeline.resources.opensky import OpenSkyAdapter, FlightRecord


SAMPLE_RESPONSE = [
    {
        "icao24": "a1b2c3",
        "firstSeen": 1704067200,
        "estDepartureAirport": "KJFK",
        "lastSeen": 1704074400,
        "estArrivalAirport": "KLAX",
        "callsign": "AA100   ",
        "estDepartureAirportHorizDistance": 500,
        "estDepartureAirportVertDistance": 50,
        "estArrivalAirportHorizDistance": 600,
        "estArrivalAirportVertDistance": 60,
        "departureAirportCandidatesCount": 1,
        "arrivalAirportCandidatesCount": 1,
    }
]


def test_fetch_departures_returns_arrow_table():
    adapter = OpenSkyAdapter()
    with patch("pipeline.resources.opensky.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SAMPLE_RESPONSE,
            raise_for_status=lambda: None,
        )
        table = adapter.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    assert isinstance(table, pa.Table)
    assert "icao24" in table.column_names
    assert "callsign" in table.column_names
    assert "first_seen" in table.column_names
    assert table.num_rows == 1


def test_callsign_is_stripped():
    adapter = OpenSkyAdapter()
    with patch("pipeline.resources.opensky.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SAMPLE_RESPONSE,
            raise_for_status=lambda: None,
        )
        table = adapter.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    assert table.column("callsign")[0].as_py() == "AA100"


def test_fetch_departures_handles_404():
    adapter = OpenSkyAdapter()
    with patch("pipeline.resources.opensky.httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        table = adapter.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    assert isinstance(table, pa.Table)
    assert table.num_rows == 0


def test_fetch_departures_handles_null_response():
    adapter = OpenSkyAdapter()
    with patch("pipeline.resources.opensky.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: None,
            raise_for_status=lambda: None,
        )
        table = adapter.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    assert isinstance(table, pa.Table)
    assert table.num_rows == 0
