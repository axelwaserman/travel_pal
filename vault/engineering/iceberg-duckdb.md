---
type: engineering
title: Iceberg ↔ DuckDB Read/Transform Topology
tags: [engineering, iceberg, duckdb, dbt, nessie]
status: draft
updated: 2026-08-08
---

# Iceberg ↔ DuckDB Read/Transform Topology

> Where DuckDB reads Iceberg, where transforms run, where interactive reads run. Consumes [[ingestion-backfill]]. Feeds [[frontend-backend-split]], [[serving-service]]. See [[architecture-summary]].

## Three DuckDB execution contexts (keep them separate)

| Context | Reads | Writes | Where it runs | Cost profile |
|---|---|---|---|---|
| **A. Batch transform** (dbt + DuckDB) | Iceberg tables via Nessie | Parquet marts + Iceberg feature tables | Dagster worker | Backend compute, scheduled only |
| **B. Backend serving** (DuckDB embedded in FastAPI) | Pre-materialized **feature Parquet** (not raw Iceberg) | — | Serving service | Per-request; must be fast |
| **C. Edge** (DuckDB-WASM) | **Public aggregate Parquet** byte-ranges over HTTP | — | Browser | ~$0 backend (see [[frontend-backend-split]]) |

Rule: **only context A touches raw Iceberg.** B and C read narrow, pre-shaped Parquet so neither pays Iceberg-scan/planning cost on the request path.

## A. How dbt+DuckDB reads Iceberg

- Current transforms already run in **DuckDB dialect** against Iceberg via the Nessie REST catalog (`pipeline/transforms/`, `macros/setup_iceberg.sql`). Keep single-engine (per `CLAUDE.md` — no Trino/Spark; `tech_product_Architecture.txt`'s sqlglot/Trino transpilation layer is **not** adopted, single-engine DuckDB wins on ops).
- Read path: DuckDB `iceberg` extension `iceberg_scan(<table>)` (or PyIceberg → Arrow → DuckDB register) reading Iceberg metadata from Nessie, data from SeaweedFS S3 (`httpfs`, path-style, ssl off — matches `frontend_exports._configure_s3`).
- Marts are materialized as **Parquet to `s3://raw-flights/warehouse/marts/*.parquet`** via dbt `config(location=...)` (existing `agg_*` pattern). Reuse verbatim.

## New: feature tables (for ML + serving)

Two new dbt/Dagster outputs beyond the current descriptive marts:

1. **`marts/feat_route_base_rates.parquet`** — the booking-time base-rate feature grain (see [[feature-contract]]): one row per `(carrier, origin, dest, dep_hour_bucket, dow, month)` with historical `on_time_ratio`, `cancel_rate`, delay `p50/p90`, `n`.
2. **`signals.metar` Iceberg table** — historized fresh weather for ML training ([[ingestion-backfill]] §2).

Serving (context B) reads #1 directly as Parquet; batch scoring joins #1 × model artifact.

## Nessie branching (operational)

- `main` = published state read by transforms/serving.
- `backfill/*` and `schema/*` branches for isolated loads + breaking schema changes; merge to `main` atomically ([[ingestion-backfill]] §1.4).
- Serving + edge always read `main` (or a pinned snapshot id for reproducible B2B feed responses — see [[serving-service]] calibration metadata).

## Why not read Iceberg live at serve time

- Iceberg scan = manifest read + file pruning + S3 range fetches → tens–hundreds of ms of variable planning latency. Unacceptable inside a p95 < 300 ms budget ([[serving-service]]).
- Pre-materialized Parquet keyed on the lookup grain → single narrow file, predictable latency, and DuckDB can `read_parquet` a byte-range. Same trick that makes the edge tier cheap.

## Handoffs
- → [[frontend-backend-split]]: which Parquet is public (edge) vs private (backend-only).
- → [[serving-service]]: feature-Parquet grain + snapshot-pinning.
- → [[staff-ml-engineer]]: `feat_route_base_rates` + `signals.metar` are the training inputs.

## Open questions
- [ ] DuckDB `iceberg` extension maturity for our Nessie/PyIceberg version vs PyIceberg→Arrow register — bench both. `#task/eng 🔼`
- [ ] Snapshot-pinning strategy for reproducible B2B responses. `#task/eng`

## Sources
- Repo: `pipeline/transforms/` (dbt models, `macros/setup_iceberg.sql`), `pipeline/pipeline/assets/frontend_exports.py`, `frontend/src/db/client.ts` — accessed 2026-08-08
- `CLAUDE.md` (single-engine DuckDB, dbt), `tech_product_Architecture.txt` §3.5 — accessed 2026-08-08
