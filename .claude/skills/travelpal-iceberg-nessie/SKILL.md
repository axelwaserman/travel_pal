---
name: travelpal-iceberg-nessie
description: Use when writing or modifying code that interacts with the PyIceberg + Project Nessie stack in TravelPal — including catalog initialization, namespace or table creation, schema definition, or schema evolution. Also use when debugging catalog connection failures, SeaweedFS S3 routing issues, or NestedField ID conflicts.
---

# TravelPal — PyIceberg + Project Nessie Patterns

## Topology

| Environment | Nessie REST endpoint |
|---|---|
| Local dev | `http://localhost:19120/api/v1` |
| Docker Compose | `http://nessie:19120/api/v1` |

Default branch: `main`. Nessie provides Git-like branching over Iceberg table metadata.

## NessieResource

`NessieResource` is a frozen Pydantic `BaseModel`. The catalog is built lazily via `cached_property`.

```python
from functools import cached_property

from pydantic import BaseModel, ConfigDict
from pyiceberg.catalog import Catalog, load_catalog


class NessieResource(BaseModel):
    endpoint: str

    model_config = ConfigDict(frozen=True)

    @cached_property
    def catalog(self) -> Catalog:
        return load_catalog(
            "nessie",
            **{
                "type": "rest",
                "uri": self.endpoint,
                "warehouse": "s3://raw-flights/warehouse",
            },
        )
```

`catalog` is a `cached_property` — access as `nessie.catalog`, never `nessie.catalog()`.

The `endpoint` is the full Nessie REST API base (e.g. `http://localhost:19120/api/v1`). PyIceberg's REST catalog uses this to discover the catalog API.

## Schema Definition

```python
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, LongType

raw_flights_schema = Schema(
    NestedField(1, "icao24", StringType(), required=False),
    NestedField(2, "callsign", StringType(), required=False),
    NestedField(3, "first_seen", LongType(), required=False),
    NestedField(4, "last_seen", LongType(), required=False),
    NestedField(5, "est_departure_airport", StringType(), required=False),
    NestedField(6, "est_arrival_airport", StringType(), required=False),
)
```

The first argument to `NestedField` is a stable integer field ID. Field IDs are permanent identifiers used by Iceberg for schema evolution. Never reuse or reorder them. When adding a new field, assign the next highest unused ID.

## Table Creation (idempotent)

```python
catalog = nessie.catalog
if not catalog.table_exists("flights.raw_flights"):
    catalog.create_namespace_if_not_exists("flights")
    catalog.create_table("flights.raw_flights", schema=raw_flights_schema)
```

- Always guard `create_table` with `table_exists` — Nessie raises on duplicate creation.
- `create_namespace_if_not_exists` is idempotent and safe to call on every run.
- Table identifiers use `.` as the namespace separator: `"flights.raw_flights"`.

## Dependency

```
pyiceberg[s3fs]>=0.8
```

There is no `nessie` extra in PyIceberg. Nessie integration uses the built-in REST catalog (`type="rest"`) pointed at the Nessie REST API endpoint.

## Common Mistakes

| Mistake | Fix |
|---|---|
| `nessie.catalog()` with parentheses | `nessie.catalog` — it is a `cached_property`, not a method |
| Reusing a NestedField ID during schema evolution | Assign the next highest unused ID |
| Using `NessieResource` as a plain class | It is a Pydantic `BaseModel(frozen=True)` |
| Calling `create_table` without an existence check | Guard with `catalog.table_exists(...)` first |
| Wrong warehouse path | Must be `s3://raw-flights/warehouse`, not `s3://raw-flights` |
