---
type: sales
title: Metering Unit — What We Charge For
tags: [sales, pricing, metering]
status: draft
updated: 2026-08-08
---

# Metering Unit

> Defines the billable unit before any tier can be priced. Grounded in [[differentiation-thesis]] (edge DuckDB-WASM ≈ $0 to serve) and [[research-summary]] (data access is the binding cost constraint). Feeds [[tier-matrix]], [[unit-economics]], and the gating list in [[pricing-summary]].

## The core decision: meter the *fresh fetch + inference*, not the pageview

TravelPal has two fundamentally different cost profiles, and conflating them would either bankrupt the free tier or throttle the acquisition wedge. We split the product into **three metered classes** and charge only where marginal cost is real.

| Class | What it is | Marginal cost driver | Metered? |
|-------|-----------|----------------------|----------|
| **A. Descriptive analytics view** | Route/carrier historical reliability, on-time distributions, shopping cuts — served by **DuckDB-WASM over Parquet byte-ranges at the edge** | ~$0 backend compute (client CPU + CDN egress only) | **No** — unlimited, this is the acquisition engine ([[differentiation-thesis]] §1) |
| **B. Live prediction** | One per-flight/route/time forecast that triggers a **fresh-signal fetch (weather/NOTAM) + model inference** returning calibrated `P(delay)`, `P(delay ≥ Xh)`, expected minutes + confidence band | **Weather API call (measured ~$0.0015)** + inference + NOTAM lookup | **Yes — this is the primary metering unit** |
| **C. B2B API call** | A programmatic request to the prediction/feed endpoint (per-flight or batch), SLA-backed, with calibration metadata | Same as B, plus SLA/support overhead | **Yes — metered per query, AeroAPI-style** |

## Definition of the primary unit: **1 Live Prediction (LP)**

> **1 LP = one forecast that causes a fresh-signal fetch and/or a model inference for a specific flight instance (carrier + route + departure datetime).**

Precise rules so the meter is unambiguous for [[staff-product-engineer]]:

- **A repeat forecast for the same flight instance within a TTL window (proposed 60 min) = 0 LP** (served from cache). Prevents refresh-spam from inflating cost *and* user bills.
- **A booking-time route query that returns only historical base rates (no fresh fetch) = 0 LP** — it is Class A, served at the edge.
- **A day-of forecast with fresh weather/NOTAM fusion = 1 LP.**
- **Alerts/watchlist re-evaluations count as LPs** (each scheduled re-score that hits fresh signals), because they drive recurring weather-API cost — but are heavily amortized by shared caching (below).

## Cost-driver nuance: caching collapses marginal cost

Weather and NOTAM state are **shared across all flights at the same airport × hour**. A single cached `(airport, hour)` weather pull (measured ~$0.0015) serves *every* prediction touching that airport that hour. So:

- The **first** prediction for a cold `(airport, hour)` pays the full fetch.
- The **Nth** prediction for a hot hub-hour pays ≈ $0.
- Inference (a gradient-boosted model on CPU behind FastAPI) is **assumed** near-free per call (~$0.00005, *assumed* — flag for verification).

Implication for pricing: **the LP meter overstates true cost** for high-traffic routes and understates it for obscure ones. We price the LP off a *blended* cost (see [[unit-economics]]) and use caching + degrade-to-cached behavior to keep the tail bounded.

## Why not meter dashboard loads or seats?

- **Dashboard loads** are Class A (~$0) — metering them would tax the exact free experience that acquires users, contradicting the [[differentiation-thesis]] cost-structure edge.
- **Seat-based** pricing fits the B2B **Team** tier (travel managers, [[personas]] P3) as a floor, but the **API/feed** (P3/P4) is inherently usage-shaped — insurers score portfolios in bursts. So B2B = **usage-based (LP/API call) with a seat or platform minimum**, not pure seats.

## Handoff → [[staff-product-engineer]]

Meter and enforce at the **LP boundary** (the fresh-fetch/inference call), never at the edge-analytics boundary. See the full metered/rate-limited/gated list in [[pricing-summary]].

## Sources

- [OpenWeather One Call 3.0 pricing (~$0.0015/call, 1,000 calls/day free)](https://openweathermap.org/api/one-call-3) — accessed 2026-08-08 *(measured; verify current list price)*
- [FlightAware AeroAPI pricing — per-query, from $0.002](https://www.flightaware.com/commercial/aeroapi/) — accessed 2026-08-08 *(measured B2B benchmark)*
- Cross-refs: [[differentiation-thesis]], [[research-summary]], [[personas]]
