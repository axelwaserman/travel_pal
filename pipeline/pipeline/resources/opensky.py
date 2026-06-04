import asyncio
import functools
import json
import os
import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

import pyarrow as pa
from dagster import ConfigurableResource
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator
from pyreqwest.client import Client, ClientBuilder

# Fixture JSON files contain arrays of OpenSky flight records (loose dicts
# before pydantic validation). `Any` is justified — fields vary by endpoint
# and we re-validate via OpenSkyFlight.model_validate downstream.
_JsonObject = dict[str, Any]


BASE_URL = "https://opensky-network.org/api/flights"
# OpenSky rejects queries spanning >2 days with HTTP 400.
_MAX_CHUNK_DAYS = 2

# OAuth2 token endpoint for OpenSky's Keycloak realm.
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/"
    "protocol/openid-connect/token"
)
# Refresh proactively once we are within this many seconds of the token's
# expiry, to avoid losing in-flight requests to a token that expires mid-call.
_TOKEN_REFRESH_MARGIN_S = 60.0


class OpenSkyFlight(BaseModel):
    icao24: str | None = None
    callsign: str | None = None
    first_seen: int | None = Field(None, alias="firstSeen")
    last_seen: int | None = Field(None, alias="lastSeen")
    est_departure_airport: str | None = Field(None, alias="estDepartureAirport")
    est_arrival_airport: str | None = Field(None, alias="estArrivalAirport")

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @field_validator("callsign", mode="before")
    @classmethod
    def strip_callsign(cls, v: str | None) -> str | None:
        if not v:
            return None
        stripped = v.strip()
        return stripped or None


def _date_chunks(start: str, end: str) -> list[tuple[int, int]]:
    current = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    chunks: list[tuple[int, int]] = []
    while current < end_dt:
        chunk_end = min(current + timedelta(days=_MAX_CHUNK_DAYS), end_dt)
        chunks.append((int(current.timestamp()), int(chunk_end.timestamp())))
        current = chunk_end
    return chunks


def _to_arrow(records: list[OpenSkyFlight]) -> pa.Table:
    return pa.table({
        "icao24": [r.icao24 for r in records],
        "callsign": [r.callsign for r in records],
        "first_seen": [r.first_seen for r in records],
        "last_seen": [r.last_seen for r in records],
        "est_departure_airport": [r.est_departure_airport for r in records],
        "est_arrival_airport": [r.est_arrival_airport for r in records],
    })


async def _do_fetch_chunk(
    client: Client,
    endpoint: str,
    airport_icao: str,
    begin: int,
    end: int,
    bearer: str | None = None,
) -> list[OpenSkyFlight]:
    """Fetch one time-window chunk from OpenSky. Accepts the client explicitly
    so it can be unit-tested without touching cached_property descriptors.

    When ``bearer`` is set, the request is authenticated with an
    ``Authorization: Bearer <token>`` header.
    """
    builder = client.get(endpoint).query(
        {"airport": airport_icao, "begin": begin, "end": end}
    )
    if bearer:
        builder = builder.header("Authorization", f"Bearer {bearer}")
    response = await builder.build().send()
    if response.status == 404:
        return []
    if response.status != 200:
        body = await response.text()
        raise RuntimeError(
            f"OpenSky {endpoint} returned {response.status}: {body[:500]}"
        )
    raw: list[dict] = await response.json() or []
    return [OpenSkyFlight.model_validate(r) for r in raw]


def _load_fixture(fixture_dir: str, endpoint: str, airport_icao: str) -> list[_JsonObject]:
    """Load a JSON fixture file for the given endpoint and airport.

    File naming convention: ``{endpoint}s_{airport_icao_lower}.json``
    e.g. ``departures_kjfk.json`` or ``arrivals_kjfk.json``.

    Returns an empty list when the file does not exist so callers treat a
    missing fixture as zero results rather than raising. A corrupt file
    raises ``ValueError`` — silent decode failures would mask broken
    fixtures and produce confusing zero-row test runs.

    .. note::
        This helper is intended **only** for fixture-based testing.  It is
        never called when ``OPENSKY_FIXTURE_DIR`` is unset.
    """
    filename = f"{endpoint}s_{airport_icao.lower()}.json"
    path = Path(fixture_dir) / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        try:
            data: list[_JsonObject] = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed fixture: {path}") from exc
    return data


T = TypeVar("T")


def with_valid_token(
    method: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]:
    """Decorator: ensure the OAuth2 token is valid before invoking the wrapped coroutine.

    Skips the check entirely when running in fixture mode (OPENSKY_FIXTURE_DIR set),
    so stub-mode tests never need credentials.
    """

    @functools.wraps(method)
    async def wrapper(self: "OpenSkyResource", *args: Any, **kwargs: Any) -> T:
        if not os.environ.get("OPENSKY_FIXTURE_DIR"):
            await self._ensure_token_valid()
        return await method(self, *args, **kwargs)

    return wrapper


class OpenSkyResource(ConfigurableResource):
    """OpenSky historical flights API client with OAuth2 client_credentials.

    Acquires and caches a bearer token, refreshing proactively when within
    ``_TOKEN_REFRESH_MARGIN_S`` of expiry. Concurrent refresh attempts are
    serialized via an ``asyncio.Lock`` with a double-checked fast path.

    **Fixture mode**: when ``OPENSKY_FIXTURE_DIR`` is set, all HTTP (including
    token fetch) is bypassed; records load from JSON files on disk. Files must
    follow the naming convention ``{endpoint}s_{airport_icao_lower}.json``
    (e.g. ``departures_kjfk.json``). Records are filtered to those whose
    ``firstSeen`` timestamp falls within the requested date window.
    Do **not** set ``OPENSKY_FIXTURE_DIR`` in production.
    """

    client_id: str = ""
    client_secret: str = ""

    _token: str | None = PrivateAttr(default=None)
    _expires_at: float = PrivateAttr(default=0.0)
    # Lazily initialised inside `_ensure_token_valid` to avoid binding the lock
    # to the wrong event loop (Dagster may construct the resource outside the
    # asset's loop).
    _lock: asyncio.Lock | None = PrivateAttr(default=None)

    @cached_property
    def _auth_client(self) -> Client:
        return (
            ClientBuilder()
            .connect_timeout(timedelta(seconds=5))
            .timeout(timedelta(seconds=30))
            .build()
        )

    @cached_property
    def _api_client(self) -> Client:
        return (
            ClientBuilder()
            .base_url(BASE_URL + "/")
            .connect_timeout(timedelta(seconds=5))
            .timeout(timedelta(seconds=30))
            .build()
        )

    async def _ensure_token_valid(self) -> None:
        # Fast path: no lock if token still has > margin seconds left.
        if (
            self._token is not None
            and self._expires_at - time.monotonic() >= _TOKEN_REFRESH_MARGIN_S
        ):
            return
        # Lazy lock init: safe under Dagster's single-thread-per-asset-run
        # execution model; not safe across threads.
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            # Re-check inside the lock — another coroutine may have refreshed
            # while we waited.
            if (
                self._token is not None
                and self._expires_at - time.monotonic() >= _TOKEN_REFRESH_MARGIN_S
            ):
                return
            await self._refresh_token()

    async def _refresh_token(self) -> None:
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "OpenSkyResource requires client_id and client_secret to be set "
                "(via OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET env vars)"
            )
        response = await (
            self._auth_client.post(OPENSKY_TOKEN_URL)
            .form(
                {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                }
            )
            .build()
            .send()
        )
        if response.status != 200:
            body = await response.text()
            raise RuntimeError(
                f"OpenSky token endpoint returned {response.status}: {body[:500]}"
            )
        data = await response.json()
        access_token = data.get("access_token") if isinstance(data, dict) else None
        expires_in = data.get("expires_in") if isinstance(data, dict) else None
        if (
            not access_token
            or not isinstance(expires_in, (int, float))
            or isinstance(expires_in, bool)
        ):
            raise RuntimeError(
                f"OpenSky token response missing access_token or expires_in: {data}"
            )
        self._token = access_token
        self._expires_at = time.monotonic() + float(expires_in)

    @with_valid_token
    async def fetch_departures(
        self, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        return await self._fetch("departure", airport_icao, start_date, end_date)

    @with_valid_token
    async def fetch_arrivals(
        self, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        return await self._fetch("arrival", airport_icao, start_date, end_date)

    async def _fetch(
        self, endpoint: str, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        fixture_dir = os.environ.get("OPENSKY_FIXTURE_DIR")
        if fixture_dir:
            # Sync return inside async fn — fixture mode reads from disk, no
            # awaitable work. Caller awaits the coroutine the same way.
            return self._fetch_from_fixture(
                fixture_dir, endpoint, airport_icao, start_date, end_date
            )

        all_records: list[OpenSkyFlight] = []
        for begin, end in _date_chunks(start_date, end_date):
            # Re-check token between chunks: a multi-week ingest may outlast
            # OpenSky's ~30min token TTL. The fast path is a single attribute
            # compare when the token is still fresh.
            await self._ensure_token_valid()
            chunk = await self._fetch_chunk(endpoint, airport_icao, begin, end)
            all_records.extend(chunk)
        return _to_arrow(all_records)

    def _fetch_from_fixture(
        self,
        fixture_dir: str,
        endpoint: str,
        airport_icao: str,
        start_date: str,
        end_date: str,
    ) -> pa.Table:
        """Return records from a fixture file, filtered to the requested window.

        Records whose ``firstSeen`` timestamp falls within [begin, end) for
        any chunk of the requested date range are included.  For typical
        single-day fixture windows this is equivalent to returning all records
        that overlap the date range.
        """
        raw_records = _load_fixture(fixture_dir, endpoint, airport_icao)
        if not raw_records:
            return _to_arrow([])

        chunks = _date_chunks(start_date, end_date)
        if not chunks:
            return _to_arrow([])

        window_begin = chunks[0][0]
        window_end = chunks[-1][1]

        matched: list[OpenSkyFlight] = []
        for raw in raw_records:
            first_seen = raw.get("firstSeen")
            if first_seen is not None and window_begin <= first_seen < window_end:
                matched.append(OpenSkyFlight.model_validate(raw))

        return _to_arrow(matched)

    async def _fetch_chunk(
        self, endpoint: str, airport_icao: str, begin: int, end: int
    ) -> list[OpenSkyFlight]:
        # Pure HTTP helper: callers (`_fetch`) are responsible for ensuring
        # `self._token` is still fresh before invoking. The current bearer
        # is forwarded as an `Authorization: Bearer <token>` header.
        return await _do_fetch_chunk(
            self._api_client,
            endpoint,
            airport_icao,
            begin,
            end,
            bearer=self._token,
        )
