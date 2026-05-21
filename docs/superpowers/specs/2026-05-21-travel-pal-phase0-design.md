# TravelPal — Phase 0 Design Spec
**Date:** 2026-05-21
**Scope:** Milestone 0 — Functioning ingestion, transformation, and frontend exposure for a single airport

---

## 1. Vision Recap

TravelPal transforms a user's personal travel history from static logs into prescriptive, data-driven routing advice. The core value proposition: *"We analyze your past so your future travels better."*

Phase 0 has one goal: prove the full data pipeline works end-to-end for a single airport before adding any complexity.

---

## 2. Scope

### In scope
- Single airport historical flight performance data (e.g. JFK, ICAO: KJFK)
- Complete pipeline: OpenSky batch pull → Iceberg/Nessie/SeaweedFS → dbt-duckdb aggregations → DuckDB-WASM frontend
- UI features F1.1 (flight lookup) and F1.2 (timeliness dashboard) from the MVP spec
- sqlglot transpilation pattern established (ANSI SQL → DuckDB dialect at build time)

### Out of scope
- Redis, Go ingest service, Go API Gateway, presigned URL vending
- Multi-airport, GTFS/transit legs, personal itinerary upload
- Adaptive bandwidth switching (requires Go Gateway)
- Advisory/recommendation engine
- Auth and multi-tenancy
- UI features F1.3 (carrier comparison) and F1.4 (temporal heatmap) — Phase 0 dbt models don't include carrier or hour-of-day dimensions; deferred to Phase 1

### Success criteria
A working DuckDB-WASM frontend queries pre-aggregated flight performance data for a single airport, sourced from a complete Dagster pipeline run, with no manual data manipulation steps.

---

## 3. Infrastructure

### Docker Compose services

| Service | Port | Role |
|---|---|---|
| `postgres` | 5432 | Dagster run storage and event log |
| `nessie` | 19120 | Iceberg catalog — Git-branched table metadata |
| `seaweedfs-master` | 9333 | SeaweedFS master node |
| `seaweedfs-volume` | 8080 | SeaweedFS volume node, S3-compatible API |
| `dagster-webserver` | 3000 | Asset catalog, lineage, monitoring UI |
| `dagster-daemon` | — | Schedules, sensors, backfill engine |

Total: 6 services. No Redis, no Go, no ClickHouse.

### Version constraints
- DuckDB ≥ 1.4.0 everywhere — Dagster workers, dbt-duckdb adapter, and WASM bundle must be version-matched to ensure Iceberg write format compatibility (full Iceberg write support landed in 1.4.0)
- PyIceberg for raw table registration with Nessie catalog
- dbt-duckdb adapter for transformation layer

---

## 4. Data Source

**OpenSky Network** (https://opensky-network.org) for Phase 0.

Rationale:
- Free bulk historical data available as Parquet by time range and ICAO airport code
- No API cost, no rate-limit risk during active development
- Sufficient fidelity for delay/timeliness analytics (departure/arrival timestamps, flight identifiers, aircraft registration)

**Aviationstack** remains an option for Phase 1 if richer delay-reason metadata is needed (airline-reported delay codes, gate assignments). The ingestion asset is written with a thin source adapter interface — swapping data source is a one-file change.

---

## 5. Dagster Asset Topology

Three assets, all scoped to a single airport for Phase 0.

```
raw_flights
  ← Python: fetch OpenSky bulk Parquet for configured date range and airport ICAO
  ← writes raw Parquet files to SeaweedFS
  ← PyIceberg registers/updates table in Nessie catalog

transformed_flights  (dbt-duckdb Dagster asset)
  ← reads raw Iceberg table via DuckDB 1.4.0
  ← executes dbt models: delay metrics, on-time ratio, cancellation rate
  ← writes aggregated Iceberg tables back to Nessie/SeaweedFS via DuckDB Iceberg writes

frontend_exports
  ← materializes query-ready Parquet slices to a public SeaweedFS prefix
  ← these are the files DuckDB-WASM fetches directly in the browser
```

### Partitioning strategy — DEFERRED
The partitioning topology is an explicit open decision for Milestone 1 planning. Questions to resolve at that session:

- Single monolithic table partitioned by `date + airport` vs. per-airport asset instances
- Dagster partition definitions: daily cadence? monthly? backfill window?
- How partition granularity affects DuckDB-WASM byte-range fetch efficiency
- Whether Dagster `DynamicPartitionsDefinition` (per-airport) or `MultiPartitionsDefinition` (date × airport) better fits the Phase 1 multi-airport expansion

For Phase 0, the single-airport scope means these decisions don't block progress. Assets are implemented without Dagster partition definitions and refactored in Milestone 1.

---

## 6. Transformation Layer

**dbt-duckdb** with DuckDB 1.4.0 as the execution engine.

### dbt models for Phase 0

| Model | Type | Output |
|---|---|---|
| `stg_flights` | Staging | Cast and clean raw OpenSky fields |
| `fct_flight_performance` | Fact | One row per flight: scheduled vs actual timestamps, delay minutes, on-time flag (≤15 min), cancelled flag |
| `agg_route_timeliness` | Aggregate | Per-route: avg delay, on-time ratio, cancellation rate |
| `agg_daily_timeliness` | Aggregate | Per-day: same metrics, for the timeliness dashboard |

### sqlglot transpilation pattern
ANSI-compliant SQL is the canonical source. At dbt compile time, sqlglot transpiles models to DuckDB dialect. Pre-compiled syntax trees are bundled as static assets in the React/Vite build. This pattern is established in Phase 0 even though it is simple — so the infrastructure exists before Phase 1 demands it at scale.

---

## 7. Frontend

**React + Vite + DuckDB-WASM**

### Phase 0 behaviour
- DuckDB-WASM fetches Parquet directly from a SeaweedFS bucket configured with public-read access (no auth — bucket ACL is a scaffold-time task)
- No adaptive bandwidth switching (deferred until Go API Gateway exists in Phase 2)
- Pre-compiled DuckDB SQL dialect bundles served as Vite static assets

### UI deliverables

**F1.1 — Flight Lookup Engine**
Query box accepting flight number or route pair. Returns a performance summary card: on-time ratio, average delay, cancellation rate over the loaded historical window.

**F1.2 — Historic Timeliness Dashboard**
Visual modules showing:
- Average delay volatility
- Outright cancellation probability
- On-time arrival ratio (≤15-minute variance threshold)

Sourced from `agg_route_timeliness` and `agg_daily_timeliness` dbt models.

---

## 8. Open Decisions

| Decision | Status | Target milestone |
|---|---|---|
| Iceberg table partitioning strategy | Open | Milestone 1 planning |
| Dagster asset topology (per-airport vs. monolithic table) | Open | Milestone 1 planning |
| Aviationstack vs. OpenSky for Phase 1 (live/richer data) | Open | Phase 1 kickoff |
| SeaweedFS S3 multipart upload configuration specifics | Resolve at scaffold | Phase 0 |
| DuckDB version pinning across all three execution environments | Resolve at scaffold | Phase 0 |

---

## 9. Deferred Architecture (Phase 1+)

| Component | Deferred to |
|---|---|
| Redis ingestion buffer | Phase 3 (real-time requirement) |
| Go ingest service | Phase 3 |
| Go API Gateway + presigned URL vending | Phase 2 (auth requirement) |
| Adaptive bandwidth switching | Phase 2 |
| Multi-airport / GTFS transit legs | Phase 1 |
| Personal itinerary upload (CSV/JSON) | Phase 2 |
| Advisory/recommendation engine | Phase 4 |
| Carrier comparison matrix (F1.3) | Phase 1 |
| Temporal bottleneck heatmap (F1.4) | Phase 1 |
