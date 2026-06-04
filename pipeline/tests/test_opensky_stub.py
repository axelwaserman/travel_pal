"""Unit tests for OpenSkyResource fixture (stub) mode.

These tests verify behaviour when OPENSKY_FIXTURE_DIR is set.  No network
requests are made — if any test passes without pyreqwest mocks in place, it
proves the HTTP path was never reached.  In particular, the @with_valid_token
decorator must skip OAuth2 token acquisition when fixture mode is active.
"""

import json
import os
import pathlib

import pyarrow as pa
import pytest

from pipeline.resources.opensky import OpenSkyResource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"

# The real fixture files live in pipeline/tests/fixtures/ and have 7 records
# each for KJFK on 2024-01-01 (firstSeen timestamps in [1704088800, 1704153600)).
_START_DATE = "2024-01-01"
_END_DATE = "2024-01-02"

# An airport whose fixture files do not exist.
_UNKNOWN_AIRPORT = "ZZZZ"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fixture_mode_loads_departures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_departures returns a non-empty Arrow table from the fixture file."""
    monkeypatch.setenv("OPENSKY_FIXTURE_DIR", str(_FIXTURE_DIR))

    adapter = OpenSkyResource()
    table = await adapter.fetch_departures("KJFK", _START_DATE, _END_DATE)

    assert isinstance(table, pa.Table)
    assert table.num_rows == 7, f"expected 7 rows, got {table.num_rows}"
    # Verify a known field from the first fixture record.
    callsigns = [v.as_py() for v in table.column("callsign")]
    assert "AAL100" in callsigns


@pytest.mark.asyncio
async def test_fixture_mode_loads_arrivals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_arrivals returns a non-empty Arrow table from the fixture file."""
    monkeypatch.setenv("OPENSKY_FIXTURE_DIR", str(_FIXTURE_DIR))

    adapter = OpenSkyResource()
    table = await adapter.fetch_arrivals("KJFK", _START_DATE, _END_DATE)

    assert isinstance(table, pa.Table)
    assert table.num_rows == 7, f"expected 7 rows, got {table.num_rows}"
    callsigns = [v.as_py() for v in table.column("callsign")]
    assert "BAW178" in callsigns


@pytest.mark.asyncio
async def test_fixture_mode_returns_empty_when_file_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When OPENSKY_FIXTURE_DIR is set but no file exists for the airport,
    the adapter returns an empty Arrow table rather than raising."""
    monkeypatch.setenv("OPENSKY_FIXTURE_DIR", str(_FIXTURE_DIR))

    adapter = OpenSkyResource()
    table = await adapter.fetch_departures(_UNKNOWN_AIRPORT, _START_DATE, _END_DATE)

    assert isinstance(table, pa.Table)
    assert table.num_rows == 0


@pytest.mark.asyncio
async def test_fixture_mode_filters_by_date_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Only records whose firstSeen falls within the requested window are returned."""
    # Build a synthetic fixture with one record inside and one outside the window.
    inside_record = {
        "icao24": "aabbcc",
        "firstSeen": 1704096000,  # 2024-01-01 08:00 UTC — inside [Jan 1, Jan 2)
        "lastSeen": 1704106800,
        "callsign": "TST001",
        "estDepartureAirport": "KJFK",
        "estArrivalAirport": "KLAX",
    }
    outside_record = {
        "icao24": "ddeeff",
        "firstSeen": 1704153600,  # 2024-01-02 00:00 UTC — equal to end, excluded
        "lastSeen": 1704164400,
        "callsign": "TST002",
        "estDepartureAirport": "KJFK",
        "estArrivalAirport": "KORD",
    }
    fixture_path = tmp_path / "departures_kjfk.json"
    fixture_path.write_text(json.dumps([inside_record, outside_record]))

    monkeypatch.setenv("OPENSKY_FIXTURE_DIR", str(tmp_path))

    adapter = OpenSkyResource()
    table = await adapter.fetch_departures("KJFK", "2024-01-01", "2024-01-02")

    assert table.num_rows == 1
    assert table.column("callsign")[0].as_py() == "TST001"


@pytest.mark.asyncio
async def test_fixture_mode_validates_pydantic_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All fixture records parse cleanly through OpenSkyFlight validation."""
    monkeypatch.setenv("OPENSKY_FIXTURE_DIR", str(_FIXTURE_DIR))

    adapter = OpenSkyResource()
    dep_table = await adapter.fetch_departures("KJFK", _START_DATE, _END_DATE)
    arr_table = await adapter.fetch_arrivals("KJFK", _START_DATE, _END_DATE)

    # If Pydantic validation failed, model_validate would have raised.
    assert dep_table.num_rows > 0
    assert arr_table.num_rows > 0
    # icao24 values should all be non-null strings.
    for val in dep_table.column("icao24"):
        assert val.as_py() is not None
    for val in arr_table.column("icao24"):
        assert val.as_py() is not None
