---
type: engineering
title: Frontend ↔ Backend Data Boundary
tags: [engineering, frontend, boundary, duckdb-wasm, api, metering, b2c]
status: draft
updated: 2026-08-10
---

# Frontend ↔ Backend Data Boundary

> The explicit line between edge-cached free data and API-metered paid data. Consumes [[iceberg-duckdb]], [[differentiation-thesis]] (cost-to-serve edge). Feeds [[product-shape-by-tier]], [[serving-service]]. See [[architecture-summary]].

## The boundary rule (one sentence)

**If it is a pure function of stale, public, historical aggregates → ship it to the browser as Parquet (edge, free, ~$0). If it needs freshness, model inference, personalization, or must be metered/gated → it lives behind the API.**

This is the cost model: the free route-shopping tier costs ~nothing because it serves stale, public, cacheable aggregates; everything with marginal cost sits behind metering. **DuckDB-WASM is now a *nice-to-have*** (per PR #13) — the browser-compute path is one way to serve those aggregates, but a plain server-rendered/JSON fallback is equally acceptable. Frontend stack is **React/TypeScript**.

## Edge side (free, public aggregate Parquet — WASM optional)

Reuses the existing path, repointed to **Cloudflare R2**: dbt marts → `frontend_exports` asset → **public R2 bucket** → DuckDB-WASM `read_parquet(<public url>)` **or** a server-rendered fallback (`frontend/src/db/queries.ts`).

| Surface | Existing mart | Public? |
|---|---|---|
| Route reliability / route-shopping | `route_timeliness.parquet` | ✅ |
| Carrier vs carrier on a route | `route_timeliness` + `carrier_cancellations` | ✅ |
| Cancellation rates (carrier/route) | `carrier_cancellations.parquet`, `route_cancellations.parquet` | ✅ |
| Daily/seasonal timeliness, hour×DOW heatmap | `daily_timeliness.parquet` (+ new hour×dow agg) | ✅ |
| **Booking-time base rate** ("this route is typically 78% on-time") | new `route_base_rates` slice, **pre-binned** | ✅ (it's stale + aggregate) |

**Safe to make public** because BTS is public domain ([[LICENSING.md]]) and the data is aggregated (no per-flight PII, no fresh signal, nothing metered). Cache-friendly: immutable Parquet, long `Cache-Control`, versioned by airport prefix (`{ICAO}/...`).

## Backend side (metered API — [[serving-service]])

| Surface | Why it can't be edge |
|---|---|
| **Live per-flight prediction** `P(delay≥Xh)` + bands | Needs model inference + fresh-signal fusion |
| **Day-of alerts** (≥3–6h lead) | Needs near-real-time signals + push; time-varying |
| **Fresh-signal-adjusted risk** | Weather/GDP/late-aircraft not in public Parquet |
| Anything gated by the daily cap | Metering only enforceable server-side |

(No B2B feed — B2C only.)

## Why gating must be server-side

The edge bucket is **publicly readable** (R2 public bucket). Anything in it is effectively ungateable and uncacheable-per-user. Therefore:
- **Never** put fresh signals, predictions, or per-user data in the public bucket.
- All metering/cap enforcement happens at the API (Redis token bucket keyed on **device/session id**, 5/day in MVP — see [[serving-service]] §rate-limiting).

## Legacy note (not adopted)
`tech_product_Architecture.txt` §1.3/§3.3 proposes a **low-bandwidth fallback** where a Go gateway proxies DuckDB compute + presigned-URL vending. We keep the *concept* (backend can serve compact JSON when the browser can't run WASM) but implement it in the **FastAPI** serving service, not a separate Go gateway (stack is Python — `AGENTS.md`). Presigned-URL vending only becomes relevant if/when per-user private data (Phase 2 personal history) lands; the free descriptive tier stays fully public-Parquet.

## Handoffs
- → [[product-shape-by-tier]]: maps each surface to Free / Plus (B2C).
- → [[serving-service]]: everything on the backend side is that service's responsibility.
- → [[marketing]]: the public edge surfaces are what the landing page can expose for free with no per-view cost ("best-fitting flight for your buck").

## Open questions
- [ ] Highcharts is **non-commercial licensed** ([[LICENSING.md]]) — must swap to ECharts/uPlot before any paid launch; affects edge bundle. `#task/eng 🔼`
- [ ] WASM fallback threshold + compact-JSON endpoint shape. `#task/eng 🔽`

## Sources
- Repo: `frontend/src/db/queries.ts`, `client.ts`, `pipeline/pipeline/assets/frontend_exports.py`, `.env.example`, `LICENSING.md` — accessed 2026-08-10
- [Cloudflare R2 public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/) — accessed 2026-08-10
