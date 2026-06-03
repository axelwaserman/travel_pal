import pytest
import pyarrow as pa
from unittest.mock import AsyncMock, MagicMock, patch
from pipeline.resources.opensky import (
    OpenSkyAdapter,
    OpenSkyFlight,
    _date_chunks,
    _do_fetch_chunk,
    _to_arrow,
)


SAMPLE_RESPONSE = [
    {
        "icao24": "a1b2c3",
        "firstSeen": 1704067200,
        "estDepartureAirport": "KJFK",
        "lastSeen": 1704074400,
        "estArrivalAirport": "KLAX",
        "callsign": "AA100   ",
        "estDepartureAirportHorizDistance": 500,
        "departureAirportCandidatesCount": 1,
    }
]


def test_opensky_flight_strips_callsign():
    flight = OpenSkyFlight.model_validate(SAMPLE_RESPONSE[0])
    assert flight.callsign == "AA100"


def test_opensky_flight_whitespace_callsign_returns_none():
    flight = OpenSkyFlight.model_validate({**SAMPLE_RESPONSE[0], "callsign": "   "})
    assert flight.callsign is None


def test_opensky_flight_empty_callsign_returns_none():
    flight = OpenSkyFlight.model_validate({**SAMPLE_RESPONSE[0], "callsign": ""})
    assert flight.callsign is None


def test_opensky_flight_maps_aliases():
    flight = OpenSkyFlight.model_validate(SAMPLE_RESPONSE[0])
    assert flight.first_seen == 1704067200
    assert flight.last_seen == 1704074400
    assert flight.est_departure_airport == "KJFK"
    assert flight.est_arrival_airport == "KLAX"


def test_opensky_flight_ignores_extra_fields():
    flight = OpenSkyFlight.model_validate(SAMPLE_RESPONSE[0])
    assert not hasattr(flight, "estDepartureAirportHorizDistance")


def test_to_arrow_produces_correct_schema():
    flight = OpenSkyFlight.model_validate(SAMPLE_RESPONSE[0])
    table = _to_arrow([flight])
    assert isinstance(table, pa.Table)
    assert table.num_rows == 1
    assert set(table.column_names) == {
        "icao24", "callsign", "first_seen", "last_seen",
        "est_departure_airport", "est_arrival_airport",
    }


def test_to_arrow_empty():
    table = _to_arrow([])
    assert table.num_rows == 0


def test_date_chunks_splits_by_7_days():
    # 2024-01-01 → 2024-01-22 = 21 days = exactly 3 × 7-day chunks
    chunks = _date_chunks("2024-01-01", "2024-01-22")
    assert len(chunks) == 3
    for begin, end in chunks:
        assert end - begin <= 7 * 86400


def test_date_chunks_single_window():
    chunks = _date_chunks("2024-01-01", "2024-01-05")
    assert len(chunks) == 1


@pytest.mark.asyncio
async def test_fetch_departures_returns_arrow_table():
    expected_flight = OpenSkyFlight.model_validate(SAMPLE_RESPONSE[0])

    # Patch at the class level (not instance) to avoid touching the frozen instance.
    # OpenSkyAdapter._fetch_chunk is an unbound method on the class, so patch.object
    # on the *class* replaces the descriptor without mutating any instance.
    with patch.object(
        OpenSkyAdapter,
        "_fetch_chunk",
        new=AsyncMock(return_value=[expected_flight]),
    ):
        adapter = OpenSkyAdapter()
        table = await adapter.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    assert isinstance(table, pa.Table)
    assert table.num_rows == 1
    assert table.column("callsign")[0].as_py() == "AA100"


@pytest.mark.asyncio
async def test_fetch_chunk_handles_404():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 404
    mock_req = MagicMock()
    mock_req.build.return_value.send = AsyncMock(return_value=mock_response)
    mock_client.get.return_value.query.return_value = mock_req

    result = await _do_fetch_chunk(mock_client, "departure", "KJFK", 0, 86400)

    assert result == []


@pytest.mark.asyncio
async def test_fetch_chunk_handles_empty_response():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=None)
    mock_req = MagicMock()
    mock_req.build.return_value.send = AsyncMock(return_value=mock_response)
    mock_client.get.return_value.query.return_value = mock_req

    result = await _do_fetch_chunk(mock_client, "departure", "KJFK", 0, 86400)

    assert result == []
