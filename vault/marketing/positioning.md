---
type: marketing
title: Positioning — Wedge, Statement & Grid
tags: [marketing, brand, positioning]
status: draft
updated: 2026-08-08
---

# Positioning

> Consumes [[competitors]], [[differentiation-thesis]], [[personas]], [[research-summary]]. Sets the position [[messaging]] and [[lead-gen-plan]] execute against. Uses working name **Glasswing** (see [[naming]]).

## The single sharpest wedge

> **We show our work.** Every other predictor is a black box that gives you a number; Glasswing gives you an **auditable, backtested reliability read on the *route* — so you can shop for the flight least likely to burn your day** — and serves it at near-zero cost. The wedge is **transparency + route-shopping + cost-to-serve**, never accuracy.

Grounding: prediction is commoditized to $0 by Google/airlines and we cannot out-predict FlightAware Foresight ([[differentiation-thesis]] §"cannot win"). So we do **not** compete on the number. We compete on *how the number is made* (glass-box, calibrated, published methodology) and on a *decision the incumbents don't serve well* (which carrier/time on a route is structurally most reliable).

## One-line positioning statement

**For** travelers and travel-risk teams who don't trust a black-box "your flight might be delayed" flag, **Glasswing** is a **transparent flight-reliability engine** that turns open historical performance + fresh conditions into a **calibrated, explainable route forecast** — **unlike** Google Flights, Flighty, or FlightAware, whose predictions are opaque and priced for either ads or enterprises, **Glasswing publishes its methodology and serves the analytics for free.**

## Positioning grid

Two axes chosen to isolate our whitespace:
- **X — Opaque black-box ↔ Transparent / auditable**
- **Y — Single-flight tracking ↔ Route/portfolio decision-making**

```
                 Route / portfolio decision-making
                              ▲
        Cirium ▐              │              ▐ ★ GLASSWING
     (enterprise,│            │            (transparent, route-shopping,
      opaque,    │            │             free edge tier + auditable B2B feed)
      pricey)    │            │
   ───────────── ┼──────────────────────────► Transparent / auditable
  Opaque         │            │
   FlightAware   │            │
   Foresight ▐   │   Google   │
   (B2B black    │   Flights ▐│
    box)         │  (free,    │
                 │   opaque)  │  DelayGuard.ai ▐ (free, thin, unproven)
        Flighty ▐│            │
     (opaque ML, │            │
      iOS tracker)│           │
                              ▼
                  Single-flight tracking
```

Reading: incumbents cluster **opaque**; consumer tools cluster **single-flight tracking**. The **transparent × route/portfolio** quadrant (top-right) is open — that is Glasswing's position, spanning a free consumer route-shopping surface and an auditable B2B feed.

## Positioning vs each competitor (the counter-line)

| Competitor | Their strength | Our counter (honest) |
|------------|----------------|----------------------|
| **Google Flights** | Free, in-path, weeks-ahead, confidence-gated | We don't beat their reach — we beat their *opacity*: show the methodology + a route-shopping cut Google doesn't surface |
| **Flighty** | Polished iOS tracker, paid predictive alerts (~$60/yr) | Cross-platform + web; *route-shopping analytics*, not personal tracking; transparent method |
| **FlightAware Foresight** | Best-in-class operator ML | We're not more accurate — we're **auditable and cheap**, and consumer-/mid-market-facing, not enterprise-priced |
| **Cirium** | Deep enterprise data | Same transparency + a fraction of the cost via edge DuckDB; mid-market/insurer entry point |
| **AirHelp / Hopper** | Monetize the *action* (claim/rebook) | We're the *upstream* signal + we hand off to an action partner ([[tier-matrix]] affiliate) — complementary, not competitive |

## Honesty guardrails (binding — coordinate w/ [[staff-ml-engineer]])

- Market **probabilistic, calibrated** estimates. Never "we guarantee," never a fabricated accuracy %. The viral "89.3% / MIT / 7.2B records" Google stats are **likely fabricated** — never repeat ([[research-summary]]).
- Uncertainty bands are a **feature we show**, not a weakness we hide (they're free in every tier, [[tier-matrix]]).
- "Transparent" is a promise: the public methodology/backtest page ([[lead-gen-plan]]) must actually exist.

## Market/geo note

Lean **EU** for the action/insurance angle: EU261 economics are stronger and the US DOT compensation rule was withdrawn 2025-11-17 ([[research-summary]] finding 5). Data-freshness/global claims are capped by BTS (US-only, ~3-mo lag) + OpenSky non-commercial terms — do not overclaim coverage ([[differentiation-thesis]]).

## Handoff

- → [[messaging]]: turn this wedge into persona/tier value props + landing copy.
- → [[lead-gen-plan]]: the public transparency/stats page is the top-of-funnel proof of this position.

## Sources

- Positioning derived from [[competitors]], [[differentiation-thesis]], [[personas]], [[research-summary]] (primary URLs there).
- [Foresight — FlightAware](https://www.flightaware.com/commercial/foresight/) — accessed 2026-08-08 *(measured, competitor framing)*
- [Incoming flight data for OTAs/TMCs/insurers — VariFlight DataWorks](https://dataworks.variflight.com/blog/predicting-delays-with-incoming-flights-for-otas-tmcs-and-insurance/) — accessed 2026-08-08 *(measured, B2B positioning language reference)*
