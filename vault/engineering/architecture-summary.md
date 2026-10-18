---
type: engineering
title: Product Architecture Summary
tags: [engineering, architecture, moc, summary, handoff, r2, b2c]
status: draft
updated: 2026-08-10
---

# Product Architecture Summary

> System diagram + handoff index for the predictive pivot. MOC for [[ingestion-backfill]], [[iceberg-duckdb]], [[frontend-backend-split]], [[feature-contract]], [[serving-service]], [[product-shape-by-tier]]. Consumes [[research-summary]], [[personas]].

> [!note] Product decisions locked in PR #13 review
> **B2C only** (B2B is dead). Working name **FlightPal** (marketing evaluating). Positioning = **"guarantee the best-fitting flight for your buck"**, not "transparency." Stack: **Python 3.14**, **React/TypeScript**. Lakehouse = **Cloudflare R2 + R2 Data Catalog, no Nessie, no data-versioning**. **MVP = limited mode (5 free route searches/day)**; full pricing not in phase 1. **DuckDB-WASM demoted to nice-to-have.** Priority: backfill US delay columns first, start forward daily non-US ingestion now.

## One-paragraph thesis

BTS (public-domain, US, ~3mo-stale) is the **commercial-safe historical spine**, stored as Iceberg on **Cloudflare R2** via **R2 Data Catalog** (no versioning). OpenSky stays **free-product/backtest-only** (non-commercial); live/global signals need a **budgeted commercial-clean feed**. The product wins by **finding the traveller the best-fitting flight for their money** (route-shopping + cheap-to-serve base rates), not by out-predicting incumbents. **B2C only.** Architecture split physically: stale public aggregates → cheap edge (DuckDB-WASM, *nice-to-have*); fresh signals + calibrated inference → **FastAPI** (MVP: 5 free searches/day).

## Text system diagram

```
 SOURCES                    ORCHESTRATION (Dagster)              STORAGE (Cloudflare R2 + R2 Data Catalog / Iceberg)
 ─────────                  ───────────────────────              ───────────────────────────────────────────────────
 BTS PREZIP (public) ─┐     bts_delay_backfill (label FIRST) ──► flights.bts_on_time (Iceberg, delay label)
 AeroDataBox (comm.) ─┼───► daily_nonus_ingest (start NOW) ────► flights.nonus_daily  (accrue non-US history)
 OpenSky (free/bktst)─┤                                       └► flights.nonus_backtest (non-commercial, isolated)
 NOAA METAR/TAF      ─┤     fresh_signals_poll ────┬──────────► signals.metar (Iceberg, training)
 FAA NAS/NOTAM       ─┘                            └──────────► Redis hot cache (serve-time)
                            dbt+DuckDB transforms ────────────► marts/*.parquet  +  feat_route_base_rates.parquet
                            batch_score (ML artifact) ────────► base-rate predictions (Parquet/Redis)
                                     │
        ┌────────────────────────────┴───────────────────────────────┐
        ▼                                                              ▼
  frontend_exports asset                                     FastAPI serving service (B2C)
  → public bucket (edge, nice-to-have)                       → reads feat Parquet + Redis fresh signals
        │                                                    → model.predict() → calibrated P(delay≥Xh)+bands
        ▼                                                    → metering: 5 free searches/day (MVP)
  DuckDB-WASM (browser)                                              │
  route-shopping, cancellation, heatmaps                            ▼
        └──────────────► BOUNDARY ([[frontend-backend-split]]) ◄──── live prediction, alerts (later)
        stale+public+aggregate → edge   |   fresh|inference|metered → backend
```

## Decisions (with status)

| # | Decision | Status |
|---|---|---|
| 1 | BTS = commercial-safe spine; **drop single-airport filter → nationwide** ([[ingestion-backfill]] §1.1) | proposed |
| 2 | **Backfill US delay columns FIRST** (label already in ZIPs) + **start daily non-US ingestion now** ([[ingestion-backfill]] build-order, [[historical-nonus-sources]]) | **priority** |
| 3 | Idempotency: **overwrite-by-`year_month`** not bare append — the sole backfill-safety mechanism ([[ingestion-backfill]] §1.3) | proposed (correctness gap) |
| 4 | **Cloudflare R2 + R2 Data Catalog; drop Nessie; no data-versioning** ([[iceberg-duckdb]]) | **locked (PR #13)** |
| 5 | Raw Iceberg **never on the request path**; serve from pre-materialized Parquet ([[iceberg-duckdb]]) | proposed |
| 6 | **FastAPI**, **functional small per-module files** (per-module `models.py`), Python 3.14 ([[serving-service]]) | proposed, Pre-Code Gate |
| 7 | Data boundary enforced **physically** (public bucket vs metered API); DuckDB-WASM **nice-to-have** ([[frontend-backend-split]]) | proposed |
| 8 | Output = **calibrated `P(delay≥Xh)` + bands + reason codes** ([[feature-contract]] §C) | binding (from [[research-summary]]) |
| 9 | **B2C only**; **MVP = 5 free searches/day**, full pricing later ([[product-shape-by-tier]]) | **locked (PR #13)** |
| 10 | Positioning = **"best-fitting flight for your buck"**; name → **FlightPal** (marketing) | **locked (PR #13)** |

## Feature-contract headline (the [[staff-ml-engineer]] seam)

Model consumes: **§A historical** base rates `(carrier,origin,dest,hour,dow,month)` — on-time ratio, cancel rate, delay p50/p90, sample size, congestion/carrier indices (batch, ≤3mo stale) **+ §B fresh** (day-of only) — origin METAR/TAF risk, GDP/ground-stop, late-aircraft (commercial feed). Returns **§C**: calibrated `P(delay≥{15,60,180})`, expected minutes + p10/p90 band, cancel prob, reason codes, confidence, `model_version`. Fresh features carry `observed_at`; past SLA → base-rate fallback + wider band. Full table: [[feature-contract]].

## Data volumes (estimated)

10-yr nationwide BTS ≈ **72M rows ≈ 2–4 GB Parquet**; backfill download ≈ **4.8 GB**, ~30–90 min at 8-way. Serving p95 target **< 300 ms** (day-of), **< 120 ms** (booking-time). Storage on R2 ≈ **€1/mo** ([[data-acquisition-scan]] §3). Math in [[ingestion-backfill]] §1.2 and [[serving-service]].

## Handoff index

| To | What they get | What we need back |
|---|---|---|
| [[staff-ml-engineer]] | [[feature-contract]] (§A/§B inputs, §C output), training tables, batch/online split | agree feature vector; hit calibration bar; artifact interface |
| [[security-engineer]] | [[serving-service]] (device-id metering, fresh-pull paths), public-bucket boundary | threat model: cost/abuse attacks, metering integrity, input validation |
| [[staff-platform-engineer]] | R2 + R2 Data Catalog, always-on ASGI + Redis + Dagster hosting split | low-ops host + autoscale + cost model |
| [[marketing]] | public route-shopping surfaces free-to-expose; positioning = **best-fitting flight for your buck**; name **FlightPal** | landing copy + rename decision |

## Top open questions

1. **Commercial-clean live-status feed in budget, or MVP = stale-US-BTS base rates only?** gates the day-of/fresh story. `#task/eng 🔺`
2. Calibration bar vs incumbents — can we hit it? ⛓ [[staff-ml-engineer]]. `#task/ml 🔺`
3. NOAA/FAA + gov-OTP redistribution terms for the free tier. `#task/eng 🔼`
4. R2 Data Catalog migration from the current Nessie+SeaweedFS wiring. `#task/eng ⛓ [[staff-platform-engineer]]`

## Files written / updated (this pass)
`vault/engineering/`: [[ingestion-backfill]], [[iceberg-duckdb]], [[frontend-backend-split]], [[feature-contract]], [[serving-service]], [[product-shape-by-tier]], [[data-acquisition-scan]], [[data-sources-apac-me]], [[historical-nonus-sources]], [[architecture-summary]].

## Sources
- Repo vault [[research-summary]], [[personas]], [[competitors]], [[demand-evidence]] — accessed 2026-08-10
- Codebase: `pipeline/`, `frontend/`, `docker-compose.yml`, `AGENTS.md`, `LICENSING.md` — accessed 2026-08-10
- [Cloudflare R2 Data Catalog](https://developers.cloudflare.com/r2/data-catalog/) — accessed 2026-08-10
