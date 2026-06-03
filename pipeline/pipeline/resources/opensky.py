import json
import os
from datetime import datetime, timedelta, timezone
from functools import cached_property
from pathlib import Path

import pyarrow as pa
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pyreqwest.client import Client, ClientBuilder


BASE_URL = "https://opensky-network.org/api/flights"
_MAX_CHUNK_DAYS = 7


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
) -> list[OpenSkyFlight]:
    """Fetch one time-window chunk from OpenSky. Accepts the client explicitly
    so it can be unit-tested without touching cached_property descriptors."""
    response = await (
        client.get(endpoint)
        .query({"airport": airport_icao, "begin": begin, "end": end})
        .build()
        .send()
    )
    if response.status == 404:
        return []
    raw: list[dict] = await response.json() or []
    return [OpenSkyFlight.model_validate(r) for r in raw]


def _load_fixture(fixture_dir: str, endpoint: str, airport_icao: str) -> list[dict]:
    """Load a JSON fixture file for the given endpoint and airport.

    File naming convention: ``{endpoint}s_{airport_icao_lower}.json``
    e.g. ``departures_kjfk.json`` or ``arrivals_kjfk.json``.

    Returns an empty list when the file does not exist so callers treat a
    missing fixture as zero results rather than raising.

    .. note::
        This helper is intended **only** for fixture-based testing.  It is
        never called when ``OPENSKY_FIXTURE_DIR`` is unset.
    """
    filename = f"{endpoint}s_{airport_icao.lower()}.json"
    path = Path(fixture_dir) / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data: list[dict] = json.load(fh)
    return data


class OpenSkyAdapter(BaseModel):
    """Async adapter for the OpenSky historical flights API.

    **Fixture mode** (testing only): when the environment variable
    ``OPENSKY_FIXTURE_DIR`` is set, the adapter reads JSON files from that
    directory instead of making HTTP requests.  Files must follow the naming
    convention ``{endpoint}s_{airport_icao_lower}.json`` (e.g.
    ``departures_kjfk.json``).  Records are filtered to those whose
    ``firstSeen`` timestamp falls within the requested date window.
    Do **not** set ``OPENSKY_FIXTURE_DIR`` in production.
    """

    username: str = ""
    password: str = ""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    @cached_property
    def _client(self) -> Client:
        builder = (
            ClientBuilder()
            .base_url(BASE_URL + "/")
            .connect_timeout(timedelta(seconds=5))
            .timeout(timedelta(seconds=30))
        )
        if self.username:
            builder = builder.basic_auth(self.username, self.password)
        return builder.build()

    async def fetch_departures(
        self, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        return await self._fetch("departure", airport_icao, start_date, end_date)

    async def fetch_arrivals(
        self, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        return await self._fetch("arrival", airport_icao, start_date, end_date)

    async def _fetch(
        self, endpoint: str, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        fixture_dir = os.environ.get("OPENSKY_FIXTURE_DIR")
        if fixture_dir:
            return self._fetch_from_fixture(fixture_dir, endpoint, airport_icao, start_date, end_date)

        all_records: list[OpenSkyFlight] = []
        for begin, end in _date_chunks(start_date, end_date):
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
        return await _do_fetch_chunk(self._client, endpoint, airport_icao, begin, end)
