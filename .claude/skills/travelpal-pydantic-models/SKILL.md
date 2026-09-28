---
name: travelpal-pydantic-models
description: Use when writing, reviewing, or modifying Pydantic models in the TravelPal pipeline — including environment-backed config classes, OpenSky API response models, Dagster op/asset config, PyArrow conversion helpers, or any model that touches dbt/Arrow type boundaries. Also use when adding validators, choosing field types, or deciding how to handle extra fields from external APIs.
---

# TravelPal Pydantic v2 Patterns

## Config via BaseSettings

All environment-backed configuration uses `BaseSettings`. Config objects are frozen after construction. No env prefix — fields map directly to env var names (e.g. `AIRPORT_ICAO`, `SEAWEEDFS_ENDPOINT`).

```python
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class PipelineConfig(BaseSettings):
    airport_icao: str
    ingest_start_date: str
    ingest_end_date: str
    # Accept both SEAWEEDFS_ENDPOINT and legacy SEAWEEDFS_S3_ENDPOINT
    seaweedfs_endpoint: str = Field(
        validation_alias=AliasChoices("SEAWEEDFS_ENDPOINT", "SEAWEEDFS_S3_ENDPOINT")
    )
    seaweedfs_access_key: str
    seaweedfs_secret_key: str
    nessie_endpoint: str
    raw_bucket: str = "raw-flights"
    export_bucket: str = "frontend-exports"
    opensky_username: str = ""
    opensky_password: str = ""

    model_config = SettingsConfigDict(frozen=True)

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls()
```

Use `SettingsConfigDict` (from `pydantic_settings`), not `ConfigDict` (from `pydantic`) — only `SettingsConfigDict` supports settings-specific keys.

`frozen=True` is mandatory on all config objects — they must be immutable after construction.

Fields with defaults (`raw_bucket`, `export_bucket`, `opensky_username`, `opensky_password`) do not need to be set in the environment.

## OpenSky Response Models

External API response models always set `extra="ignore"` and `populate_by_name=True`. OpenSky returns camelCase field names; use `Field(alias=...)` to map them to snake_case.

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

`extra="ignore"` silently drops additional fields OpenSky returns. `populate_by_name=True` lets tests construct the model using Python attribute names without needing to pass the camelCase alias.

## Validators

Use `@field_validator` with `mode="before"` for normalisation at the boundary (whitespace stripping, case normalisation). Use `@model_validator` for cross-field checks.

```python
@field_validator("icao24", mode="before")
@classmethod
def strip_whitespace(cls, v: str | None) -> str | None:
    return v.strip() if v else None
```

## Conversion to PyArrow

Serialise via `model_dump()` before passing to Arrow. Never use the deprecated `.dict()`.

```python
import pyarrow as pa

def records_to_arrow(records: list[OpenSkyFlight]) -> pa.Table:
    return pa.Table.from_pylist([r.model_dump() for r in records])
```

`model_dump()` outputs snake_case attribute names by default. Arrow schema inference from this output is sufficient for raw-layer tables. For curated or export-layer tables, declare an explicit `pa.schema` alongside the Pydantic model so Arrow and dbt column types stay in sync.

## Dagster Config

Dagster op and asset configuration uses `dagster.Config`, not `BaseSettings`.

```python
from dagster import Config

class IngestConfig(Config):
    dry_run: bool = False
    max_chunks: int | None = None
```

`IngestConfig` is passed by Dagster at runtime; it does not read from environment variables directly.

## Rules

- `extra="ignore"` on every external API response model.
- `populate_by_name=True` on every model that uses `Field(alias=...)`.
- `SettingsConfigDict(frozen=True)` on `BaseSettings` subclasses.
- `ConfigDict(frozen=True)` on plain `BaseModel` subclasses.
- Always `model_dump()`, never `.dict()`.
- Field types use `str | None` syntax, not `Optional[str]`.
- Never use `Any`. Truly open-ended fields are typed `dict[str, object]`.
- Every field has an explicit type annotation — no bare `field()` definitions.
