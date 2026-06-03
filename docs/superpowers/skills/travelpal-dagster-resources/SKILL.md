---
name: travelpal-dagster-resources
description: Use when writing, modifying, or debugging Dagster assets in the TravelPal pipeline — specifically when wiring resources to assets, defining Definitions, writing unit tests for assets, or handling None-returning upstream dependencies.
---

# TravelPal Dagster Resource Patterns

## 1. ResourceParam annotation (CRITICAL — always required)

Without `ResourceParam`, Dagster treats a parameter as an asset input dependency and raises `DagsterInvalidDefinitionError`. Every resource parameter must be annotated with `ResourceParam[X]`.

```python
from dagster import asset, ResourceParam

@asset
def my_asset(
    pipeline_config: ResourceParam[PipelineConfig],   # resource injection
    seaweedfs: ResourceParam[SeaweedFSResource],       # resource injection
    raw_flights: pa.Table,                             # asset input (no ResourceParam)
) -> None: ...
```

Asset inputs (upstream asset outputs) receive no annotation wrapper. Resources always do.

## 2. hardcoded_resource in Definitions

Use `ResourceDefinition.hardcoded_resource()` to wrap plain Python objects when registering them in `Definitions`. This is the standard pattern for all TravelPal resources.

```python
from dagster import Definitions, ResourceDefinition

defs = Definitions(
    assets=[raw_flights, transformed_flights, frontend_exports],
    resources={
        "pipeline_config": ResourceDefinition.hardcoded_resource(cfg),
        "opensky": ResourceDefinition.hardcoded_resource(
            OpenSkyAdapter(username=cfg.opensky_username, password=cfg.opensky_password)
        ),
        "seaweedfs": ResourceDefinition.hardcoded_resource(
            SeaweedFSResource(
                endpoint=cfg.seaweedfs_endpoint,
                access_key=cfg.seaweedfs_access_key,
                secret_key=cfg.seaweedfs_secret_key,
            )
        ),
        "nessie": ResourceDefinition.hardcoded_resource(
            NessieResource(endpoint=cfg.nessie_endpoint)
        ),
    }
)
```

`OpenSkyAdapter` takes `username` and `password` as strings extracted from `cfg` — it does not accept a `PipelineConfig` directly.

## 3. _resources_or_empty (unit test compatibility)

`PipelineConfig.from_env()` raises `pydantic.ValidationError` when required environment variables are absent. Wrapping resource construction in `_resources_or_empty()` allows `from pipeline import defs` to succeed in unit tests that do not set up env vars.

```python
def _resources_or_empty() -> dict:
    try:
        return _make_resources()
    except (KeyError, ValidationError):
        return {}

defs = Definitions(
    assets=[...],
    resources=_resources_or_empty(),
)
```

In practice, `pydantic_settings` raises `ValidationError` for missing required fields. `KeyError` is caught defensively for any future dict-based lookups in `_make_resources`.

## 4. AssetIn(dagster_type=Nothing) for None-returning upstreams

When an upstream asset returns `None`, do not add a parameter for it in the downstream asset's signature. Dagster will attempt direct invocation with that parameter, causing errors in unit tests. Declare the dependency through `ins` instead.

```python
from dagster import asset, AssetIn, Nothing

@asset(ins={"transformed_flights": AssetIn(dagster_type=Nothing)})
def frontend_exports(
    pipeline_config: ResourceParam[PipelineConfig],
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None: ...
```

## 5. Testing assets directly (unit tests)

Asset functions are plain Python callables. Call them directly in unit tests — no Dagster runtime required. Pass resources as keyword arguments matching the parameter names.

`async` resource methods (like `fetch_departures`) must use `AsyncMock`:

```python
from unittest.mock import AsyncMock, MagicMock
import pyarrow as pa

def test_raw_flights_uploads_parquet():
    config = PipelineConfig(
        airport_icao="KJFK",
        ingest_start_date="2024-01-01",
        ingest_end_date="2024-01-08",
        seaweedfs_endpoint="http://localhost:8333",
        seaweedfs_access_key="admin",
        seaweedfs_secret_key="admin",
        nessie_endpoint="http://localhost:19120/api/v1",
    )
    mock_table = pa.table({"icao24": ["abc"], "callsign": ["AA1"],
                           "first_seen": [0], "last_seen": [1],
                           "est_departure_airport": ["KJFK"],
                           "est_arrival_airport": ["KLAX"]})
    opensky = MagicMock(spec=OpenSkyAdapter)
    opensky.fetch_departures = AsyncMock(return_value=mock_table)
    opensky.fetch_arrivals = AsyncMock(return_value=mock_table)
    seaweedfs = MagicMock(spec=SeaweedFSResource)
    nessie = MagicMock(spec=NessieResource)
    nessie.catalog = MagicMock()

    result = raw_flights(
        pipeline_config=config,
        opensky=opensky,
        seaweedfs=seaweedfs,
        nessie=nessie,
    )
    seaweedfs.upload_parquet.assert_called_once()
```

## Rules

- All resource params annotated with `ResourceParam[X]` — no exceptions
- `_resources_or_empty()` catches both `KeyError` and `pydantic.ValidationError`
- Prefer `ResourceDefinition.hardcoded_resource()` for plain Python objects
- Use `AssetIn(dagster_type=Nothing)` for `-> None` upstream dependencies
- Do not name params `config` — Dagster reserves that name; use `pipeline_config`
- `fetch_departures` and `fetch_arrivals` are `async` — use `AsyncMock` in tests

## Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Missing `ResourceParam` | `DagsterInvalidDefinitionError: Input asset not produced` | Add `ResourceParam[X]` annotation |
| Param named `config` | Dagster internal conflict | Rename to `pipeline_config` |
| `transformed_flights: None` in signature | Direct invocation error in tests | Use `AssetIn(dagster_type=Nothing)` |
| Catching only `KeyError` in `_resources_or_empty` | `ValidationError` propagates, import fails in tests | Catch both `KeyError` and `ValidationError` |
| `MagicMock` for async adapter methods | `TypeError: object MagicMock can't be used in 'await' expression` | Use `AsyncMock` |
| `OpenSkyAdapter()` with no args in Definitions | Resources get no credentials | Pass `username=cfg.opensky_username, password=cfg.opensky_password` |
