---
type: engineering
title: Ingestion & Backfill Design
tags: [engineering, ingestion, backfill, iceberg, dagster, data]
status: draft
updated: 2026-08-08
---

# Ingestion & Backfill Design

> How the historical spine and fresh signals get into the lakehouse. Consumes [[research-summary]] (data constraints), [[differentiation-thesis]]. Feeds [[iceberg-duckdb]], [[serving-service]], [[feature-contract]]. See [[architecture-summary]].

## 0. Binding constraints (from research)

| Constraint | Source | Design consequence |
|---|---|---|
| BTS is **US-only**, lags **up to ~3 months** | [[research-summary]], [BTS](https://www.bts.gov/) | Historical spine is stale + US-only. Cannot claim "fresh" from BTS alone. |
| BTS is **public domain** (US gov) | [[LICENSING.md]] | Safe to redistribute aggregates on the free edge tier. |
| OpenSky **prohibits commercial use** w/o paid license; thins outside EU/US | [OpenSky FAQ](https://opensky-network.org/about/faq) | OpenSky is fine for a non-commercial MVP/backtest, **but must be dropped or license-upgraded before any paid tier ships**. Gating decision — see Open Questions. |

**Design stance:** BTS is the *commercial-safe historical spine*. OpenSky stays a *dev/backtest-only* source. Freshness + global coverage require a budgeted paid feed (Cirium / FlightAware AeroAPI / commercial OpenSky) — treated as a pluggable adapter, not assumed present.

## 1. Historical spine (BTS → Iceberg)

### 1.1 Change vs current code
Current `bts_on_time` asset (`pipeline/pipeline/assets/bts_on_time.py`) **filters to a single airport IATA** to keep the table small (Phase 1 demo, KJFK). A route-shopping product needs the **nationwide** graph (any origin×dest) so we can rank carriers/times across routes. **Design change:** drop the airport filter for the spine; keep per-airport filtering only in the `frontend_exports` slice (already done there). Volume math below is sized for nationwide.

### 1.2 Volume math (mark: **estimated**)
- BTS On-Time reporting ≈ **~600–650k rows / month** nationwide, ~7M rows/yr (estimated from reporting-carrier scheduled domestic volume).
- Backfill window: **10 yr (2016-01 → 2025-12) = 120 months** → **~72M rows** total.
- Raw monthly ZIP ≈ **~25–50 MB**; uncompressed CSV ≈ **~200–250 MB** (~110 cols). We project **10 cols** (see `_BTS_COLUMNS`) → per-row footprint tiny.
- Post-projection Parquet (Iceberg, zstd): ~**30–60 B/row** → **~2–4 GB total** for 10 yr. Fits DuckDB single-node easily.
- Download budget: 120 × ~40 MB ≈ **~4.8 GB**. Sequential at the 600s/month timeout is hours; **8-way concurrent partition backfill → ~30–90 min** wall-clock (estimated, network-bound).

### 1.3 Partition + idempotency (reuse existing pattern)
- Keep `MonthlyPartitionsDefinition` (start `2016-01-01`). Each partition = one `YYYY-MM`; deterministic key.
- **Idempotent append with dedup**: current code does bare `iceberg_table.append(table)` — re-running a partition double-appends. Add a **delete-by-partition then append** (Iceberg `overwrite` filtered on `year_month = <key>`) so a re-materialized month is replace-not-duplicate. This is the one correctness gap to close for safe backfills.
- **Cache layer already correct**: raw ZIP cached to `bts-raw` bucket keyed `YYYY-MM.zip`; re-runs skip download. Keep.
- Schema drift: existing `update_schema().union_by_name(_SCHEMA)` before append is the right idempotent guard (Iceberg schema evolution). Keep.

### 1.4 Nessie branch-per-backfill
1. Create branch `backfill/bts-2016-2025` off `main` (Nessie ref).
2. Materialize all 120 partitions onto the branch (Dagster asset writes target the branch ref).
3. Validate on branch (row counts per month vs BTS published totals; null-key rate; dbt tests).
4. **Merge branch → main** as one atomic catalog commit → readers never see a half-loaded spine.
- Rationale: matches `travelpal-iceberg-nessie` skill + `tech_product_Architecture.txt` §3.2 (git-like isolation). Incremental monthly top-ups after go-live commit straight to `main` (one clean month at a time).

## 2. Fresh signals

Two sub-streams, different landing zones:

| Signal | Source (terms) | Cadence | Lands in | Rationale |
|---|---|---|---|---|
| **METAR/TAF** (weather) | NOAA Aviation Weather Center `aviationweather.gov` — **US-gov public domain** (mark: **assumed**, verify redistribution terms) | METAR hourly (+SPECI); TAF ~6h | **Hot cache (Redis)** keyed `station+hour`, TTL ~90 min; daily roll-up appended to `signals.metar` Iceberg table for training | Serve-time join needs low latency; Iceberg copy gives ML a historical weather spine for training features |
| **Ground Delay Programs / airport advisories** | FAA NAS Status / OIS (`nasstatus.faa.gov`) — US-gov (mark: **assumed**, verify) | Poll ~5–15 min | Hot cache only (ephemeral) | GDP/ground-stop is the single strongest *day-of* signal; no need to historize beyond training snapshots |
| **NOTAMs** | FAA NOTAM API (free API key, US) — international ICAO harder | Poll ~15–30 min | Hot cache | Runway/closure context; US-first |
| **Live flight status / late-aircraft** | **Paid feed required** (OpenSky non-commercial) | Near-real-time | Hot cache | The "late inbound aircraft" feature; gated behind the paid-feed decision |
| Alt weather | OpenWeather — **freemium, commercial license + rate caps** (mark: **assumed**) | — | — | Fallback only; prefer NOAA to avoid per-call cost + commercial terms |

**Batch vs near-real-time rule:** anything used only at *booking time* (base rates, seasonality) is **batch**. Anything used at *day-of* within the 3–6h lead window ([[personas]] P1) is **near-real-time → hot cache**, with a periodic Iceberg snapshot purely so ML can train on it.

## 3. Reconciliation & consistency

- **Late-arriving BTS**: BTS revises months for ~3 mo. Re-materialize the trailing 3 partitions on a schedule (`overwrite` by `year_month` from §1.3 makes this safe/idempotent).
- **Batch↔fresh consistency**: fresh signals never mutate the historical spine; they are *joined at serve time* as a delta over base rates (see [[serving-service]]). No two-writer race on Iceberg.
- **Schema evolution**: Iceberg `union_by_name` (additive only); breaking changes go through a Nessie branch + dbt contract test before merge.
- **Dedup**: BTS is authoritative per (flight_date, carrier, flight_number, origin, dest, crs_dep_time); enforce as a dbt `unique` test on the staging grain.

## 4. Dagster job map

| Job | Trigger | Assets |
|---|---|---|
| `backfill_bts` | manual / branch | `bts_on_time` (120 partitions, 8-way) |
| `bts_monthly_topup` | schedule (monthly, +offset for lag) | latest + trailing-3 re-materialize |
| `fresh_signals_poll` | sensor/schedule (5–60 min) | METAR/GDP/NOTAM → cache + snapshot |
| `feature_build` + `batch_score` | after spine update | see [[serving-service]] |

## Handoffs
- → [[iceberg-duckdb]]: table grains + Nessie branch model.
- → [[feature-contract]] / [[staff-ml-engineer]]: which signals historize (training spine) vs cache-only.
- ⛓ **[[sales]] / [[unit-economics]]**: paid-feed budget gates OpenSky-replacement + live-status feature.

## Open questions
- [ ] Secure a **commercial live-status feed** in budget, or ship MVP with **stale-US-BTS base rates only** (no live day-of)? `#task/eng 🔺 ⛓ [[sales]]`
- [ ] Confirm **NOAA/FAA redistribution terms** for the free edge tier. `#task/eng 🔼`
- [ ] Backfill depth: 10 yr vs 5 yr (recency vs sample size for rare routes). `#task/eng ⛓ [[staff-ml-engineer]]`

## Sources
- [OpenSky FAQ — commercial use](https://opensky-network.org/about/faq) — accessed 2026-08-08
- [BTS](https://www.bts.gov/) — on-time timeliness/lag — accessed 2026-08-08
- [NOAA Aviation Weather Center](https://aviationweather.gov/) — accessed 2026-08-08 *(terms need verification)*
- [FAA NAS Status](https://nasstatus.faa.gov/) — accessed 2026-08-08 *(terms need verification)*
- Repo: `pipeline/pipeline/assets/bts_on_time.py`, `resources/bts.py`, `resources/opensky.py`, `LICENSING.md` — accessed 2026-08-08
