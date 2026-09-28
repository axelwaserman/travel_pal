---
type: engineering
title: Iceberg ↔ DuckDB Read/Transform Topology
tags: [engineering, iceberg, duckdb, dbt, r2, r2-data-catalog]
status: draft
updated: 2026-08-10
---

# Iceberg ↔ DuckDB Read/Transform Topology

> Where DuckDB reads Iceberg, where transforms run, where interactive reads run. Consumes [[ingestion-backfill]]. Feeds [[frontend-backend-split]], [[serving-service]]. See [[architecture-summary]].

## Stack: Cloudflare R2 + R2 Data Catalog (no Nessie)

Per [[staff-platform-engineer]]'s proposal the lakehouse is **Cloudflare R2** (object storage) + **R2 Data Catalog** (managed Iceberg REST catalog). **Nessie is dropped** and **data-versioning is abandoned** — Iceberg's own table-level ACID commits are all the safety we need. R2's **zero egress** is the reason it beats S3/SeaweedFS for repeated training + serving reads ([[data-acquisition-scan]] §3).

## Three DuckDB execution contexts (keep them separate)

| Context | Reads | Writes | Where it runs | Cost profile |
|---|---|---|---|---|
| **A. Batch transform** (dbt + DuckDB) | Iceberg tables via **R2 Data Catalog** | Parquet marts + Iceberg feature tables on R2 | Dagster worker | Backend compute, scheduled only |
| **B. Backend serving** (DuckDB embedded in FastAPI) | Pre-materialized **feature Parquet** (not raw Iceberg) | — | Serving service | Per-request; must be fast |
| **C. Edge** (DuckDB-WASM) | **Public aggregate Parquet** byte-ranges over HTTP | — | Browser | ~$0 backend — **nice-to-have, not the core feature** ([[frontend-backend-split]]) |

Rule: **only context A touches raw Iceberg.** B and C read narrow, pre-shaped Parquet so neither pays Iceberg-scan/planning cost on the request path.

## A. How dbt+DuckDB reads Iceberg

- Transforms run in **DuckDB dialect** against Iceberg via the **R2 Data Catalog (Iceberg REST)** endpoint (replaces the current Nessie REST wiring in `pipeline/transforms/`, `macros/setup_iceberg.sql`). Keep single-engine (per `AGENTS.md` — no Trino/Spark; the legacy sqlglot/Trino transpilation layer is **not** adopted).
- Read path: DuckDB `iceberg` extension `iceberg_scan(<table>)` (or PyIceberg → Arrow → DuckDB register) reading Iceberg metadata from **R2 Data Catalog**, data from **R2** (`httpfs`, path-style S3 API).
- Marts are materialized as **Parquet on R2** via dbt `config(location=...)` (existing `agg_*` pattern, repointed from SeaweedFS to R2). Reuse the shape verbatim.

## New: feature tables (for ML + serving)

Two new dbt/Dagster outputs beyond the current descriptive marts:

1. **`marts/feat_route_base_rates.parquet`** — booking-time base-rate feature grain ([[feature-contract]]): one row per `(carrier, origin, dest, dep_hour_bucket, dow, month)` with historical `on_time_ratio`, `cancel_rate`, delay `p50/p90`, `n`.
2. **`signals.metar` Iceberg table** — historized fresh weather for ML training ([[ingestion-backfill]] §2).

Serving (context B) reads #1 directly as Parquet; batch scoring joins #1 × model artifact.

## Catalog operation (R2 Data Catalog, no versioning)

- One published state per table — **no branches, no merge, no snapshot-pinning**. Data versioning is dropped; we don't need reproducible historical replays.
- Writers commit atomically per Iceberg table; a bad partition is fixed by **idempotent re-materialize** ([[ingestion-backfill]] §1.3), not a rollback.
- Serving + edge always read the current table state.

## Why not read Iceberg live at serve time

- Iceberg scan = manifest read + file pruning + object range fetches → tens–hundreds of ms of variable planning latency. Unacceptable inside a p95 < 300 ms budget ([[serving-service]]).
- Pre-materialized Parquet keyed on the lookup grain → single narrow file, predictable latency, DuckDB can `read_parquet` a byte-range. Same trick that keeps the (nice-to-have) edge tier cheap.

## Handoffs
- → [[frontend-backend-split]]: which Parquet is public (edge) vs private (backend-only).
- → [[serving-service]]: feature-Parquet grain.
- → [[staff-ml-engineer]]: `feat_route_base_rates` + `signals.metar` are the training inputs.
- → [[staff-platform-engineer]]: R2 Data Catalog endpoint + credentials for Dagster/dbt.

## Open questions
- [ ] DuckDB `iceberg` extension compatibility with **R2 Data Catalog** (Iceberg REST) vs PyIceberg→Arrow register — bench both. `#task/eng 🔼`
- [ ] Migration of existing dbt `setup_iceberg.sql` / profiles from Nessie+SeaweedFS to R2 Data Catalog + R2. `#task/eng ⛓ [[staff-platform-engineer]]`

## Sources
- [Cloudflare R2 Data Catalog](https://developers.cloudflare.com/r2/data-catalog/) · [R2 pricing (zero egress)](https://developers.cloudflare.com/r2/pricing/) — accessed 2026-08-10
- Repo: `pipeline/transforms/` (dbt models, `macros/setup_iceberg.sql`), `pipeline/pipeline/assets/frontend_exports.py`, `frontend/src/db/client.ts` — accessed 2026-08-10
- `AGENTS.md` (single-engine DuckDB, dbt) — accessed 2026-08-10
