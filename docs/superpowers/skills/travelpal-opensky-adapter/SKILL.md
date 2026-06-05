---
name: travelpal-opensky-adapter
description: Use when writing, reviewing, or debugging any code that touches the OpenSky Network API within the TravelPal pipeline — including the OpenSkyAdapter class, flight ingestion jobs, date chunking, Pydantic response models, or any logic that calls the departure or arrival endpoints. Also use when diagnosing missing cancellation data, unexpected 403 errors, empty result sets, or callsign formatting issues traced to the OpenSky integration.
---

# TravelPal — OpenSky Network Adapter

## Base URL

```python
BASE_URL = "https://opensky-network.org/api/flights"
```

The client's `base_url` is set to `BASE_URL + "/"`. Requests use relative paths `departure` and `arrival`.

## Endpoints

| Method | Relative path | Purpose |
|--------|------|---------|
| `GET` | `departure?airport={icao}&begin={unix}&end={unix}` | Flights departing an airport in a Unix time range |
| `GET` | `arrival?airport={icao}&begin={unix}&end={unix}` | Flights arriving at an airport in a Unix time range |

`begin` and `end` are **Unix epoch integers** (seconds). Never send ISO date strings.

## Authentication

HTTP Basic Auth. Credentials are passed as constructor arguments (not `PipelineConfig` directly):

```python
OpenSkyAdapter(username=cfg.opensky_username, password=cfg.opensky_password)
```

Rules:
- Credentials are optional (`""` default) — adapter works unauthenticated for public data.
- Credentials are applied only when `username` is non-empty.
- A 403 may mean wrong credentials or a rate limit. Do not retry aggressively on 403.
- Retry with exponential backoff on 429.

## Response Shape

OpenSky returns a JSON array. Field names are camelCase. An empty range may return `[]` or HTTP 404 — both are valid and handled the same way (zero results, no error).

```json
[
  {
    "icao24": "abc123",
    "firstSeen": 1609459200,
    "lastSeen": 1609462800,
    "estDepartureAirport": "KJFK",
    "estArrivalAirport": "KLAX",
    "callsign": "AAL100  "
  }
]
```

## Pydantic Model

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

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
```

## Date Chunking

OpenSky enforces a **7-day maximum** per request. `_date_chunks` returns a list of `(begin, end)` Unix integer tuples:

```python
from datetime import datetime, timedelta, timezone

_MAX_CHUNK_DAYS = 7

def _date_chunks(start: str, end: str) -> list[tuple[int, int]]:
    current = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    chunks: list[tuple[int, int]] = []
    while current < end_dt:
        chunk_end = min(current + timedelta(days=_MAX_CHUNK_DAYS), end_dt)
        chunks.append((int(current.timestamp()), int(chunk_end.timestamp())))
        current = chunk_end
    return chunks
```

Intervals are UTC. The `begin`/`end` ints are passed directly to the `?begin=&end=` query params.

## Adapter Implementation

```python
from functools import cached_property
from datetime import timedelta
from pyreqwest.client import ClientBuilder

class OpenSkyAdapter:
    def __init__(self, username: str = "", password: str = "") -> None:
        self._username = username
        self._password = password

    @cached_property
    def _client(self):
        builder = (
            ClientBuilder()
            .base_url(BASE_URL + "/")
            .connect_timeout(timedelta(seconds=5))
            .timeout(timedelta(seconds=30))
        )
        if self._username:
            builder = builder.basic_auth(self._username, self._password)
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
        response = await (
            self._client.get(endpoint)
            .query({"airport": airport_icao, "begin": begin, "end": end})
            .build()
            .send()
        )
        if response.status == 404:
            return []
        raw: list[dict] = await response.json() or []
        return [OpenSkyFlight.model_validate(r) for r in raw]
```

The client is built lazily via `cached_property` — not injected, not a context manager. This means `OpenSkyAdapter()` is safe to register as a Dagster `hardcoded_resource`.

## Arrow Conversion

```python
import pyarrow as pa

def _to_arrow(records: list[OpenSkyFlight]) -> pa.Table:
    return pa.table({
        "icao24": [r.icao24 for r in records],
        "callsign": [r.callsign for r in records],
        "first_seen": [r.first_seen for r in records],
        "last_seen": [r.last_seen for r in records],
        "est_departure_airport": [r.est_departure_airport for r in records],
        "est_arrival_airport": [r.est_arrival_airport for r in records],
    })
```

## Known Limitations

### 1. Only completed flights
OpenSky only records flights that have both a departure and an arrival. Cancelled flights never appear. **`cancellation_rate` cannot be computed from OpenSky data.** Deferred to Phase 1.

### 2. Time range cap — 7 days per request
Always use `_date_chunks` for any range. Never exceed 7 days per request.

### 3. 403 ambiguity
A 403 can mean wrong credentials or a rate limit. Back off; do not hammer the API.

### 4. Empty range returns 404 or []
OpenSky returns HTTP 404 (no body) for time windows with no flights. `_fetch_chunk` treats 404 as an empty list. An API response of `[]` is also valid. Do not raise on either.

### 5. Trailing whitespace in callsign
`callsign` regularly has trailing spaces. The `strip_callsign` validator handles this automatically.

## Quick Reference

| Rule | Detail |
|------|--------|
| Constructor | `OpenSkyAdapter(username="", password="")` — client built lazily via `cached_property` |
| Auth | Applied only when `username` is non-empty |
| Date params | Unix epoch integers — use `_date_chunks` to convert ISO dates |
| Window | Never exceed 7 days; `_date_chunks` handles splitting |
| Empty range | 404 or `[]` — both return empty list, not an error |
| Callsign | Strip trailing whitespace via validator |
| Cancellations | Not available from OpenSky; deferred to Phase 1 |
