import asyncio
import time

import pytest
import pyarrow as pa
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.resources.opensky import (
    OpenSkyResource,
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


# ---------------------------------------------------------------------------
# OpenSkyFlight model
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# OpenSkyResource.fetch_departures (with fixture-mode bypass)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_departures_returns_arrow_table(monkeypatch, tmp_path):
    """Fixture mode bypasses HTTP entirely, so no token or chunk fetch is needed.

    We patch _fetch_chunk at the class level to ensure no network hit, but in
    practice fixture mode short-circuits before _fetch_chunk is called. This
    covers the "decorator skips token check when OPENSKY_FIXTURE_DIR set"
    contract from a different angle: we set fixture mode but still patch
    _fetch_chunk to be safe.
    """
    expected_flight = OpenSkyFlight.model_validate(SAMPLE_RESPONSE[0])

    # Patch at the class level (not instance) to avoid touching frozen attrs.
    with patch.object(
        OpenSkyResource,
        "_fetch_chunk",
        new=AsyncMock(return_value=[expected_flight]),
    ):
        # Fixture mode bypasses HTTP token fetch — no creds required.
        monkeypatch.setenv("OPENSKY_FIXTURE_DIR", str(tmp_path))
        # No fixture file exists for KJFK in tmp_path → returns empty table.
        resource = OpenSkyResource()
        table = await resource.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    # In fixture mode with no fixture file present, table is empty.
    assert isinstance(table, pa.Table)
    assert table.num_rows == 0


@pytest.mark.asyncio
async def test_fetch_departures_calls_fetch_chunk_when_no_fixture(monkeypatch):
    """When OPENSKY_FIXTURE_DIR is unset, the public path uses _fetch_chunk.

    This covers the live-API code path. We patch the token check and
    _fetch_chunk to avoid hitting any network.
    """
    monkeypatch.delenv("OPENSKY_FIXTURE_DIR", raising=False)
    expected_flight = OpenSkyFlight.model_validate(SAMPLE_RESPONSE[0])

    with patch.object(
        OpenSkyResource,
        "_ensure_token_valid",
        new=AsyncMock(return_value=None),
    ), patch.object(
        OpenSkyResource,
        "_fetch_chunk",
        new=AsyncMock(return_value=[expected_flight]),
    ):
        resource = OpenSkyResource(client_id="id", client_secret="secret")
        table = await resource.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    assert isinstance(table, pa.Table)
    assert table.num_rows == 1
    assert table.column("callsign")[0].as_py() == "AA100"


# ---------------------------------------------------------------------------
# _do_fetch_chunk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_chunk_handles_404():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 404
    mock_req = MagicMock()
    mock_req.build.return_value.send = AsyncMock(return_value=mock_response)
    mock_client.get.return_value.query.return_value = mock_req

    result = await _do_fetch_chunk(mock_client, "departure", "KJFK", 0, 86400, bearer=None)

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

    result = await _do_fetch_chunk(mock_client, "departure", "KJFK", 0, 86400, bearer=None)

    assert result == []


@pytest.mark.asyncio
async def test_fetch_chunk_passes_bearer_header_when_set():
    """When a bearer token is provided, the request builder must receive an
    Authorization: Bearer <token> header before .build() is called."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=[])

    # Chain: client.get(endpoint).query(...).header("Authorization", ...).build().send()
    after_query = MagicMock()
    after_header = MagicMock()
    after_header.build.return_value.send = AsyncMock(return_value=mock_response)
    after_query.header.return_value = after_header
    mock_client.get.return_value.query.return_value = after_query

    result = await _do_fetch_chunk(
        mock_client, "departure", "KJFK", 0, 86400, bearer="tok_abc"
    )

    assert result == []
    after_query.header.assert_called_once_with("Authorization", "Bearer tok_abc")


# ---------------------------------------------------------------------------
# OAuth2 token refresh
# ---------------------------------------------------------------------------


def _make_token_response(access_token: str = "tok_xyz", expires_in: int = 1800):
    """Build a MagicMock that mimics a pyreqwest Response for a token POST."""
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(
        return_value={"access_token": access_token, "expires_in": expires_in}
    )
    response.text = AsyncMock(return_value="")
    return response


def _patch_post(resource: OpenSkyResource, response):
    """Replace resource._auth_client.post(...) so it returns a builder whose
    .form(...).build().send() yields ``response``. Returns the post MagicMock
    so callers can assert call counts.

    This monkey-patches the cached_property's already-realised value via the
    resource's __dict__ — we never let real pyreqwest run.
    """
    post_mock = MagicMock()
    fake_builder = MagicMock()
    fake_builder.form.return_value.build.return_value.send = AsyncMock(
        return_value=response
    )
    post_mock.return_value = fake_builder
    fake_client = MagicMock()
    fake_client.post = post_mock
    # Override the cached_property by stuffing into __dict__.
    resource.__dict__["_auth_client"] = fake_client
    return post_mock


@pytest.mark.asyncio
async def test_token_fetched_once_within_ttl():
    """5 sequential _ensure_token_valid() calls fetch the token exactly once."""
    resource = OpenSkyResource(client_id="id", client_secret="secret")
    post_mock = _patch_post(resource, _make_token_response(expires_in=1800))

    for _ in range(5):
        await resource._ensure_token_valid()

    assert post_mock.call_count == 1
    assert resource._token == "tok_xyz"


@pytest.mark.asyncio
async def test_token_refresh_on_expiry(monkeypatch):
    """When the cached token is within the refresh margin, the next call
    triggers a fresh POST."""
    resource = OpenSkyResource(client_id="id", client_secret="secret")
    post_mock = _patch_post(resource, _make_token_response(expires_in=1800))

    await resource._ensure_token_valid()
    assert post_mock.call_count == 1

    # Force the token to look "almost expired" (within the 60s margin).
    resource._expires_at = time.monotonic() + 30.0

    await resource._ensure_token_valid()
    assert post_mock.call_count == 2


@pytest.mark.asyncio
async def test_token_refresh_concurrent_calls_share_one_fetch():
    """10 concurrent _ensure_token_valid() coroutines must serialise via the
    asyncio.Lock and only trigger one underlying POST (double-checked
    locking)."""
    resource = OpenSkyResource(client_id="id", client_secret="secret")
    post_mock = _patch_post(resource, _make_token_response(expires_in=1800))

    await asyncio.gather(*[resource._ensure_token_valid() for _ in range(10)])

    assert post_mock.call_count == 1


@pytest.mark.asyncio
async def test_token_endpoint_non_200_raises():
    resource = OpenSkyResource(client_id="id", client_secret="secret")
    bad_response = MagicMock()
    bad_response.status = 401
    bad_response.text = AsyncMock(return_value="invalid_client")
    bad_response.json = AsyncMock(return_value={})
    _patch_post(resource, bad_response)

    with pytest.raises(RuntimeError, match="401"):
        await resource._ensure_token_valid()


@pytest.mark.asyncio
async def test_token_endpoint_missing_access_token_raises():
    resource = OpenSkyResource(client_id="id", client_secret="secret")
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value={})  # No access_token / expires_in
    response.text = AsyncMock(return_value="{}")
    _patch_post(resource, response)

    with pytest.raises(RuntimeError, match="missing access_token"):
        await resource._ensure_token_valid()


@pytest.mark.asyncio
async def test_missing_credentials_raises():
    resource = OpenSkyResource()  # no client_id / client_secret
    with pytest.raises(RuntimeError, match="OPENSKY_CLIENT_ID"):
        await resource._ensure_token_valid()


@pytest.mark.asyncio
async def test_fixture_mode_skips_token_fetch(monkeypatch, tmp_path):
    """When OPENSKY_FIXTURE_DIR is set, fetch_* must NOT call the token
    endpoint — even with empty credentials."""
    monkeypatch.setenv("OPENSKY_FIXTURE_DIR", str(tmp_path))

    resource = OpenSkyResource()  # no creds
    post_mock = _patch_post(resource, _make_token_response())

    # No fixture file exists → empty table, but the key assertion is that
    # the token POST was never made.
    table = await resource.fetch_departures("KJFK", "2024-01-01", "2024-01-02")

    assert isinstance(table, pa.Table)
    assert table.num_rows == 0
    post_mock.assert_not_called()
