---
type: engineering
title: Product Architecture Summary
tags: [engineering, architecture, moc, summary, handoff]
status: draft
updated: 2026-08-08
---

# Product Architecture Summary

> System diagram + handoff index for the predictive pivot. MOC for [[ingestion-backfill]], [[iceberg-duckdb]], [[frontend-backend-split]], [[feature-contract]], [[serving-service]], [[product-shape-by-tier]]. Consumes [[research-summary]], [[differentiation-thesis]], [[personas]].

## One-paragraph thesis

BTS (public-domain, US, ~3mo-stale) is the **commercial-safe historical spine** in Iceberg; OpenSky stays **dev/backtest-only** (non-commercial license) and any *live/global* signal requires a **budgeted paid feed**. We win on **cost-to-serve + transparency + route-shopping + a B2B feed**, not raw accuracy ([[differentiation-thesis]]). The architecture encodes that split physically: **stale public aggregates → free DuckDB-WASM edge (~$0)**; **fresh signals + calibrated model inference → metered FastAPI**.

## Text system diagram

```
 SOURCES                    ORCHESTRATION (Dagster)              STORAGE (Nessie+Iceberg / SeaweedFS)
 ─────────                  ───────────────────────              ────────────────────────────────────
 BTS PREZIP (public) ─┐     bts_on_time (monthly parts) ───────► flights.bts_on_time (Iceberg)
 OpenSky (dev-only)  ─┼───► raw_flights ──────────────────────► flights.raw_flights
 NOAA METAR/TAF      ─┤     fresh_signals_poll ────┬──────────► signals.metar (Iceberg, training)
 FAA NAS/NOTAM       ─┤                            └──────────► Redis hot cache (serve-time)
 [paid live feed]?   ─┘                                          
                            dbt+DuckDB transforms ────────────► marts/*.parquet  +  feat_route_base_rates.parquet
                            batch_score (ML artifact) ────────► base-rate predictions (Parquet/Redis)
                                     │
        ┌────────────────────────────┴───────────────────────────────┐
        ▼                                                              ▼
  frontend_exports asset                                     FastAPI serving service
  → frontend-exports bucket (ANON public)                    → reads feat Parquet + Redis fresh signals
        │                                                    → model.predict() → calibrated P(delay≥Xh)+bands
        ▼                                                    → metering / rate-limit (token bucket, per tier)
  DuckDB-WASM (browser)                                              │
  FREE edge: route-shopping,                                         ▼
  cancellation, heatmaps (~$0)                              PLUS/PRO/API: live prediction, alerts, B2B feed
        └──────────────► BOUNDARY ([[frontend-backend-split]]) ◄──────┘
        stale+public+aggregate → edge   |   fresh|inference|metered → backend
```

## Decisions (with status)

| # | Decision | Status |
|---|---|---|
| 1 | BTS = commercial-safe spine; **drop single-airport filter → nationwide** ([[ingestion-backfill]] §1.1) | proposed |
| 2 | OpenSky **non-commercial ⇒ dev/backtest only**; paid feed gates live-status feature | binding constraint |
| 3 | Idempotency fix: **overwrite-by-`year_month`** not bare append ([[ingestion-backfill]] §1.3) | proposed (correctness gap) |
| 4 | **Single-engine DuckDB**; no Trino/Spark/sqlglot transpilation ([[iceberg-duckdb]]) | confirms `CLAUDE.md` |
| 5 | Raw Iceberg **never on the request path**; serve from pre-materialized Parquet ([[iceberg-duckdb]]) | proposed |
| 6 | **FastAPI** serving service; **no Go gateway** ([[serving-service]]) | proposed, Pre-Code Gate |
| 7 | Data boundary enforced **physically** (anon public bucket vs metered API) ([[frontend-backend-split]]) | proposed |
| 8 | Output = **calibrated `P(delay≥Xh)` + bands + reason codes** ([[feature-contract]] §C) | binding (from [[research-summary]]) |
| 9 | Highcharts non-commercial ⇒ **swap before paid launch** ([[LICENSING.md]]) | flagged |

## Feature-contract headline (the [[staff-ml-engineer]] seam)

Model consumes: **§A historical** base rates `(carrier,origin,dest,hour,dow,month)` — on-time ratio, cancel rate, delay p50/p90, sample size, congestion/carrier indices (batch, ≤3mo stale) **+ §B fresh** (day-of only) — origin METAR/TAF risk, GDP/ground-stop, late-aircraft (paid). Model returns **§C**: calibrated `P(delay≥{15,60,180})`, expected minutes + p10/p90 band, cancel prob, reason codes, confidence, and `model_version`/`snapshot_id` for audit. Fresh features carry `observed_at`; if past SLA → base-rate fallback + wider band. Full table: [[feature-contract]].

## Data volumes (estimated)

10-yr nationwide BTS ≈ **72M rows ≈ 2–4 GB Parquet**; backfill download ≈ **4.8 GB**, ~30–90 min at 8-way. Serving p95 target **< 300 ms** (day-of), **< 120 ms** (booking-time). Math + assumptions in [[ingestion-backfill]] §1.2 and [[serving-service]].

## Handoff index

| To | What they get | What we need back |
|---|---|---|
| [[staff-ml-engineer]] | [[feature-contract]] (§A/§B inputs, §C output), training tables, batch/online split | agree feature vector; hit calibration bar; artifact interface |
| [[security-engineer]] | [[serving-service]] (API keys, metering, fresh-pull paths), anon-bucket boundary | threat model: cost/abuse attacks, multi-tenant isolation, input validation |
| [[staff-platform-engineer]] | always-on ASGI + Redis + Dagster + SeaweedFS hosting split | low-ops host + autoscale + cost model |
| [[sales]] | metering hooks ready; edge=free / API=metered | **[[tier-matrix]] + [[unit-economics]] + metering unit** (currently assumed) |
| [[marketing]] | public edge surfaces = free-to-expose; **never claim accuracy superiority** | positioning on transparency/route-shopping |

## Top open questions (blocking)

1. **Paid live-status feed in budget, or MVP = stale-US-BTS base rates only?** ⛓ [[sales]] — gates the whole day-of/fresh story. `#task/eng 🔺`
2. **[[sales]] must publish [[tier-matrix]]/[[unit-economics]]** — tiers + metering unit currently assumed. `#task/eng 🔺`
3. Calibration bar vs FlightAware Foresight — can we hit it? ⛓ [[staff-ml-engineer]]. `#task/ml 🔺`
4. NOAA/FAA redistribution terms for the free edge. `#task/eng 🔼`

## Files written (this pass)
`vault/engineering/`: [[ingestion-backfill]], [[iceberg-duckdb]], [[frontend-backend-split]], [[feature-contract]], [[serving-service]], [[product-shape-by-tier]], [[architecture-summary]].

## Sources
- Repo vault [[research-summary]], [[differentiation-thesis]], [[personas]], [[competitors]], [[demand-evidence]] — accessed 2026-08-08
- Codebase: `pipeline/`, `frontend/`, `docker-compose.yml`, `CLAUDE.md`, `tech_product_Architecture.txt`, `LICENSING.md`, `.env.example` — accessed 2026-08-08
