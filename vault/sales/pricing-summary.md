---
type: sales
title: Pricing Summary & Handoff — TravelPal Monetization
tags: [sales, pricing, summary, moc, handoff]
status: draft
updated: 2026-08-08
---

# Pricing Summary & Handoff

> One-page recommendation synthesizing [[metering-unit]], [[tier-matrix]], [[unit-economics]]. Grounded in [[research-summary]], [[competitors]], [[personas]], [[differentiation-thesis]]. Handoffs to [[marketing]] and [[staff-product-engineer]].

## Recommendation in three sentences

Meter the **Live Prediction (LP)** — a fresh-signal-fetch + inference forecast — and give away everything the edge serves for ~$0 (route/carrier descriptive analytics via DuckDB-WASM). Sell a thin consumer ladder (Free / Plus $39/yr / Pro $59/yr) priced to convert and cover cost, **not** as the business. **The margin is the B2B usage-based feed (Team/API)** to TMCs and parametric insurers, priced off the AeroAPI benchmark and differentiated on auditable calibration — with a rebook/insurance **action affiliate** layered on every tier as near-free-delivery upside.

## Metering unit (the one decision everything hangs on)

**1 LP = one forecast that triggers a fresh weather/NOTAM fetch and/or model inference for a specific flight instance.** Cached repeats within 60 min = 0 LP. Edge descriptive views = **not metered**. Full definition: [[metering-unit]].

## Tier matrix at a glance

| Tier | Price | LP quota | Key gate | Persona |
|---|---|---|---|---|
| **Free** | $0 | 5/day → degrade to cached | no alerts, no API | P2 / P1 trial |
| **Plus** | $39/yr | 50/day | alerts (5 flights), full route analytics | P1 |
| **Pro** | $59/yr | unlimited (fair-use 500/day) | unlimited watchlist, full history | P1 heavy |
| **Team/API** | usage + $99–$1,000/mo min | metered $0.003–0.006/LP | SLA, calibration report, feed | P3 TMC / P4 insurer |

Detail + anchoring in [[tier-matrix]].

## Unit-economics headline

- **Blended cost/LP ≈ $0.0015** (measured weather @ $0.0015, net of `(airport,hour)` caching; inference/NOTAM assumed ~$0 — *flag to verify*).
- **Free tier loses only ~$0.05–0.23/user/mo**; edge analytics are $0 → safe at scale, recovered by a **2–5% conversion** + affiliate.
- **Plus GM ~58–86%; API GM ~50–75%.** **Pro margin is fair-use-dependent** — enforce caps or it can invert.
- **Fixed infra $ is unknown** (owned by [[staff-platform-engineer]]) and sets true break-even; a **paid data feed** (if BTS/OpenSky limits force it) would raise the LP cost floor — a live gating decision. Full model: [[unit-economics]].

## Handoff → [[staff-product-engineer]]: what MUST be metered / rate-limited / gated

**Meter (count + bill):**
1. **LP boundary** — every fresh-signal-fetch/inference call, keyed to `(user, flight_instance)`; cached repeats within TTL = free.
2. **B2B API calls** — per-key, per-LP, with batch support for portfolio scoring (P4).

**Rate-limit (abuse & cost defense):**
3. Per-user LP/day quota per tier (5 / 50 / 500-soft / metered).
4. Per-IP + per-device throttle on **anonymous free** (scraping/cost-attack defense — coordinate with [[security-engineer]]).
5. Per-API-key RPS ceilings (Team 5/s, Standard 10/s, Premium 100/s — AeroAPI-style).
6. Burst caps on **cold-route fresh fetches** (the expensive tail).

**Gate (feature entitlement by tier):**
7. Proactive alerts + watchlist size; historical depth window (3mo / 12mo / full); multi-trip/itinerary risk; API + batch export; calibration/backtest metadata (B2B only). Uncertainty bands are **free** (trust-building, cheap).

**Cost ceilings / enforcement (binding):**
8. **Hard ceiling $0.002/LP.** Above it → **degrade to cached base-rate, never serve at a loss, never hard-block a paying user.**
9. **Mandatory `(airport,hour)` weather cache, 60-min TTL** — cost control, not just perf.
10. Overage = **degrade-to-cached** (Free/Plus) or **pay-per-use** (API), not silent failure.
11. Multi-vendor weather abstraction (OpenWeather ↔ Tomorrow.io) so a list-price hike doesn't blow the LP floor.

## Handoff → [[marketing]]

- Names/prices: **Free / Plus $39/yr / Pro $59/yr / Team+API (usage)**. Monthly offered at a premium; annual default.
- Value props: Free = transparent route-shopping; Plus = alerts + analytics under Flighty's price; Pro = unlimited proactive foresight; B2B = auditable, cheap calibrated feed.
- **Do NOT market on out-predicting Google/FlightAware** ([[differentiation-thesis]]) — sell transparency, route-shopping, cost-to-serve. Lean EU for the action/insurance angle.

## Open questions (owned by sales)

- [ ] Sign a **B2B design partner** (TMC or insurer) to validate API price + calibration bar before building the feed surface #task/sales 🔺 📅 2026-09-15 ⛓ [[staff-product-engineer]]
- [ ] Negotiate **rebook/insurance affiliate** rev-share rate (currently unknown — do not invent) #task/sales 🔼 📅 2026-09-30
- [ ] Confirm **inference + NOTAM per-LP cost** via load test #task/sales ⛓ [[staff-ml-engineer]] 📅 2026-09-15
- [ ] Re-price if a **paid data feed** becomes mandatory (BTS lag / OpenSky commercial bar) #task/sales ⛓ [[staff-platform-engineer]] 📅 2026-09-15

## Sources

- [OpenWeather One Call 3.0 pricing](https://openweathermap.org/api/one-call-3) — accessed 2026-08-08 *(measured)*
- [FlightAware AeroAPI pricing](https://www.flightaware.com/commercial/aeroapi/) — accessed 2026-08-08 *(measured)*
- [Flighty pricing](https://flighty.com/pricing) · [AirHelp+ pricing](https://travel-dealz.com/deal/airhelp-plus/) — accessed 2026-08-08 *(measured)*
- Cross-refs: [[metering-unit]], [[tier-matrix]], [[unit-economics]], [[research-summary]], [[competitors]], [[personas]], [[differentiation-thesis]]
