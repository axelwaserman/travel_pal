---
type: engineering
title: Frontend ↔ Backend Data Boundary
tags: [engineering, frontend, boundary, duckdb-wasm, api, metering]
status: draft
updated: 2026-08-08
---

# Frontend ↔ Backend Data Boundary

> The explicit line between edge-cached free data and API-metered paid data. Consumes [[iceberg-duckdb]], [[differentiation-thesis]] (cost-to-serve edge). Feeds [[product-shape-by-tier]], [[serving-service]]. See [[architecture-summary]].

## The boundary rule (one sentence)

**If it is a pure function of stale, public, historical aggregates → ship it to the browser as Parquet (edge, free, ~$0). If it needs freshness, model inference, personalization, or must be metered/gated → it lives behind the API.**

This *is* the business model in [[differentiation-thesis]]: the free descriptive tier costs us ~nothing because DuckDB-WASM does the compute in the user's browser over cacheable Parquet byte-ranges; everything with marginal cost or WTP sits behind metering.

## Edge side (free, DuckDB-WASM, anonymous public Parquet)

Reuses the existing path: dbt marts → `frontend_exports` asset → `frontend-exports` bucket (anonymous read) → DuckDB-WASM `read_parquet(<public url>)` (`frontend/src/db/queries.ts`).

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
| **B2B feed / batch scoring** | Metered, SLA'd, snapshot-pinned, contractual |
| Anything gated by tier/quota | Metering only enforceable server-side |

## Why gating must be server-side

The edge bucket is **anonymous-readable** (`.env.example`: `s3.configure -user=anonymous -buckets=frontend-exports -actions=Read,List`). Anything in it is effectively ungateable and uncacheable-per-user. Therefore:
- **Never** put fresh signals, predictions, or per-user data in `frontend-exports`.
- All metering/quota/tier enforcement happens at the API (token bucket keyed to API key/tier — see [[serving-service]] §rate-limiting).

## Legacy note (not adopted)
`tech_product_Architecture.txt` §1.3/§3.3 proposes a **low-bandwidth fallback** where a Go gateway proxies DuckDB compute + presigned-URL vending. We keep the *concept* (backend can serve compact JSON when the browser can't run WASM) but implement it in the **FastAPI** serving service, not a separate Go gateway (stack is Python — `CLAUDE.md`). Presigned-URL vending only becomes relevant if/when per-user private data (Phase 2 personal history) lands; the free descriptive tier stays fully public-Parquet.

## Handoffs
- → [[product-shape-by-tier]]: maps each surface to Free/Plus/Pro/API.
- → [[serving-service]]: everything on the backend side is that service's responsibility.
- → [[marketing]]: the public edge surfaces are what the landing page can expose for free with no per-view cost.

## Open questions
- [ ] Highcharts is **non-commercial licensed** ([[LICENSING.md]]) — must swap to ECharts/uPlot before any paid launch; affects edge bundle. `#task/eng 🔼`
- [ ] WASM fallback threshold + compact-JSON endpoint shape. `#task/eng 🔽`

## Sources
- Repo: `frontend/src/db/queries.ts`, `client.ts`, `pipeline/pipeline/assets/frontend_exports.py`, `.env.example`, `LICENSING.md` — accessed 2026-08-08
- `tech_product_Architecture.txt` §1.3, §3.3 — accessed 2026-08-08
