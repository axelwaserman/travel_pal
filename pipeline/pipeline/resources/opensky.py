from datetime import datetime, timedelta, timezone
from functools import cached_property

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
        return v.strip() if v else None


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


class OpenSkyAdapter(BaseModel):
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
        all_records: list[OpenSkyFlight] = []
        for begin, end in _date_chunks(start_date, end_date):
            chunk = await self._fetch_chunk(endpoint, airport_icao, begin, end)
            all_records.extend(chunk)
        return _to_arrow(all_records)

    async def _fetch_chunk(
        self, endpoint: str, airport_icao: str, begin: int, end: int
    ) -> list[OpenSkyFlight]:
        return await _do_fetch_chunk(self._client, endpoint, airport_icao, begin, end)
