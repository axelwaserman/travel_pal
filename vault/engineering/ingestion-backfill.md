---
type: engineering
title: Ingestion & Backfill Design
tags: [engineering, ingestion, backfill, iceberg, dagster, data, r2]
status: draft
updated: 2026-08-10
---

# Ingestion & Backfill Design

> How the historical spine and fresh signals get into the lakehouse. Consumes [[research-summary]] (data constraints), [[differentiation-thesis]]. Feeds [[iceberg-duckdb]], [[serving-service]], [[feature-contract]]. See [[architecture-summary]].

## 0. Binding constraints (from research)

| Constraint | Source | Design consequence |
|---|---|---|
| BTS is **US-only**, lags **up to ~3 months** | [[research-summary]], [BTS](https://www.bts.gov/) | Historical spine is stale + US-only. Cannot claim "fresh" from BTS alone. |
| BTS is **public domain** (US gov) | [[LICENSING.md]] | Safe to redistribute aggregates on the free tier. |
| OpenSky **prohibits commercial use** w/o paid license; thins outside EU/US | [OpenSky FAQ](https://opensky-network.org/about/faq) | OpenSky is fine for the **free-product / backtest** zone, **not** for any commercial-clean output. Isolate it (see [[historical-nonus-sources]]). |

**Design stance:** BTS is the *commercial-safe historical spine*. OpenSky stays a *free-product/backtest-only* source. Freshness + global coverage require a budgeted commercial-clean feed (AeroDataBox / FlightAware AeroAPI / Cirium) — a pluggable adapter, not assumed present.

## 1. Historical spine (BTS → Iceberg on R2)

> [!important] Build order (per PR #13 review)
> 1. **Backfill the US delay columns FIRST.** Widen the BTS projection to emit `DepDelay`/`ArrDelay` + actual times + cause codes (`CarrierDelay`…`LateAircraftDelay`) — the supervised delay label, already inside the ZIPs we download ([[data-acquisition-scan]] §0). Cheapest, highest-leverage step.
> 2. **Start forward daily ingestion NOW** to accrue non-US history we cannot buy deep/cheap ([[historical-nonus-sources]] §Start-now plan). Every day not captured is permanently lost.
> 3. **Then** backfill the deep US spine (below).

### 1.1 Change vs current code
Current `bts_on_time` asset (`pipeline/pipeline/assets/bts_on_time.py`) **filters to a single airport IATA** (Phase 1 demo, KJFK). A route-shopping product needs the **nationwide** graph (any origin×dest) to rank carriers/times across routes. **Design change:** drop the airport filter for the spine; keep per-airport filtering only in the export slice. Volume math below is nationwide.

### 1.2 Volume math (mark: **estimated**)
- BTS On-Time reporting ≈ **~600–650k rows / month** nationwide, ~7M rows/yr (estimated from reporting-carrier scheduled domestic volume).
- Backfill window: **10 yr (2016-01 → 2025-12) = 120 months** → **~72M rows** total.
- Raw monthly ZIP ≈ **~25–50 MB**; uncompressed CSV ≈ **~200–250 MB** (~110 cols). Projected column set (delay label + keys) stays small.
- Post-projection Parquet (Iceberg, zstd): ~**30–60 B/row** → **~2–4 GB total** for 10 yr. Fits DuckDB single-node easily.
- Download budget: 120 × ~40 MB ≈ **~4.8 GB**. Sequential at the 600s/month timeout is hours; **8-way concurrent partition backfill → ~30–90 min** wall-clock (estimated, network-bound).

### 1.3 Partition + idempotency (the correctness backbone)
- Keep `MonthlyPartitionsDefinition` (start `2016-01-01`). Each partition = one `YYYY-MM`; deterministic key.
- **Idempotent overwrite**: current code does bare `iceberg_table.append(table)` — re-running a partition double-appends. Replace with **delete-by-partition then append** (Iceberg `overwrite` filtered on `year_month = <key>`) so a re-materialized month is replace-not-duplicate. **This idempotency — not any versioning layer — is what makes backfills safe.**
- **Cache layer already correct**: raw ZIP cached to an `bts-raw` R2 bucket keyed `YYYY-MM.zip`; re-runs skip download. Keep.
- Schema drift: existing `update_schema().union_by_name(_SCHEMA)` before append is the right idempotent guard (Iceberg schema evolution). Keep.

### 1.4 Catalog: Cloudflare R2 Data Catalog (no data versioning)
- **Drop Nessie.** Per [[staff-platform-engineer]], the lakehouse uses **Cloudflare R2** (object storage) + **R2 Data Catalog** (managed Iceberg REST catalog). We **abandon data-versioning entirely** — no branch-per-backfill, no merge step. Git-like branching bought us nothing the append-mostly spine needs.
- **Safety without branching:** Iceberg tables on R2 Data Catalog are still **ACID at the table level** — each partition write is an atomic commit. Backfill correctness comes from the **idempotent overwrite-by-`year_month`** (§1.3), not from a staging branch.
- **Backfill flow:** materialize all 120 partitions straight into `flights.bts_on_time`; a failed or re-run partition overwrites cleanly. Monthly top-ups append one clean month.
- **Validation:** dbt tests run **post-load** (row counts per month vs BTS published totals, null-key rate, dedup uniqueness) — no isolated branch needed. A bad month is simply re-materialized (idempotent).

## 2. Fresh signals

Two sub-streams, different landing zones:

| Signal | Source (terms) | Cadence | Lands in | Rationale |
|---|---|---|---|---|
| **METAR/TAF** (weather) | NOAA Aviation Weather Center `aviationweather.gov` — **US-gov public domain** (mark: **assumed**, verify redistribution terms) | METAR hourly (+SPECI); TAF ~6h | **Hot cache (Redis)** keyed `station+hour`, TTL ~90 min; daily roll-up appended to `signals.metar` Iceberg table (on R2) for training | Serve-time join needs low latency; Iceberg copy gives ML a historical weather spine |
| **Ground Delay Programs / airport advisories** | FAA NAS Status / OIS (`nasstatus.faa.gov`) — US-gov (mark: **assumed**, verify) | Poll ~5–15 min | Hot cache only (ephemeral) | GDP/ground-stop is the single strongest *day-of* signal |
| **NOTAMs** | FAA NOTAM API (free API key, US) — international ICAO harder | Poll ~15–30 min | Hot cache | Runway/closure context; US-first |
| **Live flight status / late-aircraft** | **Commercial-clean feed required** (OpenSky non-commercial) | Near-real-time | Hot cache | The "late inbound aircraft" feature; gated behind the paid-feed decision |
| Alt weather | OpenWeather — **freemium, commercial license + rate caps** (mark: **assumed**) | — | — | Fallback only; prefer NOAA to avoid per-call cost + commercial terms |

**Batch vs near-real-time rule:** booking-time inputs (base rates, seasonality) are **batch**. Day-of inputs within the 3–6h lead window ([[personas]] P1) are **near-real-time → hot cache**, with a periodic Iceberg snapshot so ML can train on them.

## 3. Reconciliation & consistency

- **Late-arriving BTS**: BTS revises months for ~3 mo. Re-materialize the trailing 3 partitions on a schedule (`overwrite` by `year_month` from §1.3 makes this safe/idempotent).
- **Batch↔fresh consistency**: fresh signals never mutate the historical spine; they are *joined at serve time* as a delta over base rates (see [[serving-service]]). No two-writer race.
- **Schema evolution**: Iceberg `union_by_name` (additive only); breaking changes gated by a **dbt contract test before the write** — no branch (data-versioning is dropped, §1.4).
- **Dedup**: BTS is authoritative per (flight_date, carrier, flight_number, origin, dest, crs_dep_time); enforce as a dbt `unique` test on the staging grain.

## 4. Dagster job map

| Job | Trigger | Assets |
|---|---|---|
| `bts_delay_backfill` | manual (**do first**) | widen BTS projection → delay label + cause codes |
| `daily_nonus_ingest` | schedule (**daily, start now**) | AeroDataBox airport flight lists (EU/APAC hubs) → `flights.nonus_daily`; OpenSky → isolated `flights.nonus_backtest` |
| `backfill_bts` | manual | `bts_on_time` (120 partitions, 8-way) |
| `bts_monthly_topup` | schedule (monthly, +offset for lag) | latest + trailing-3 re-materialize |
| `fresh_signals_poll` | sensor/schedule (5–60 min) | METAR/GDP/NOTAM → cache + snapshot |
| `feature_build` + `batch_score` | after spine update | see [[serving-service]] |

## Handoffs
- → [[iceberg-duckdb]]: table grains + **R2 Data Catalog** wiring.
- → [[feature-contract]] / [[staff-ml-engineer]]: which signals historize (training spine) vs cache-only.
- ⛓ **[[staff-platform-engineer]]**: R2 + R2 Data Catalog provisioning, storage cost ([[data-acquisition-scan]] §3).

## Open questions
- [ ] Secure a **commercial-clean live-status feed** in budget, or ship MVP with **stale-US-BTS base rates only** (no live day-of)? `#task/eng 🔺`
- [ ] Confirm **NOAA/FAA redistribution terms** for the free tier. `#task/eng 🔼`
- [ ] Backfill depth: 10 yr vs 5 yr (recency vs sample size for rare routes). `#task/eng ⛓ [[staff-ml-engineer]]`

## Sources
- [OpenSky FAQ — commercial use](https://opensky-network.org/about/faq) — accessed 2026-08-10
- [BTS](https://www.bts.gov/) — on-time timeliness/lag — accessed 2026-08-10
- [Cloudflare R2 Data Catalog](https://developers.cloudflare.com/r2/data-catalog/) — accessed 2026-08-10
- [NOAA Aviation Weather Center](https://aviationweather.gov/) — accessed 2026-08-10 *(terms need verification)*
- [FAA NAS Status](https://nasstatus.faa.gov/) — accessed 2026-08-10 *(terms need verification)*
- Repo: `pipeline/pipeline/assets/bts_on_time.py`, `resources/bts.py`, `resources/opensky.py`, `LICENSING.md` — accessed 2026-08-10
