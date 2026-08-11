---
type: research
title: Differentiation Thesis — Best-Flight-For-Your-Buck (B2C)
tags: [product, research, differentiation]
status: draft
updated: 2026-08-10
---

# Differentiation Thesis

> Why a reliability-aware route-shopping product could win — and where it can't. B2C only. See [[competitors]], [[personas]], [[competitor-usecase-gap]], [[research-summary]].
>
> **Reframed 2026-08-10 (PR #13):** the wedge is the **product promise — "guarantee the best-fitting flight for your buck"** — not the tech. Edge-compute (DuckDB-WASM) is demoted from hero to a supporting nice-to-have; transparency is a trust-support, not the headline.

## The thesis (2–3 sentences)

**We help a traveler book the flight that best fits their money and their tolerance for delay** — a reliability-aware route-shopping decision (Use Case A in [[competitor-usecase-gap]]) that no consumer product does well today. Under the hood, a historical-flight lakehouse + a calibrated on-time model rank each option on **price × reliability × timing**, but the user-facing win is a **confident "book this one" recommendation**, not a raw probability or a methodology paper. We win on the **booking decision moment and the best-for-your-buck promise**, not on out-predicting Google/FlightAware's per-flight ETA.

## Where it can realistically beat incumbents

1. **The best-for-your-buck recommendation.** Google flashes a black-box "often delayed" flag on *one* flight; nobody offers a **ranked, multi-criteria** answer to "which bookable option gives me the best reliability for my price/timing?" That decision-moment product is the gap (see [[competitor-usecase-gap]]).
2. **Reliability as a first-class shopping axis.** Kayak/Google sort on price/duration/stops; we make **structural on-time reliability** a sortable, weighable criterion alongside price — purpose-built on the lakehouse's aggregate route/carrier cut.
3. **Trust through explainability (support, not headline).** A plain "why this flight" (route history, typical delay, confidence) builds trust in the recommendation. It reassures; it is **not** the thing we sell.

## Role of edge-compute / DuckDB-WASM (real, but NOT the hero)

Actioning the PR #13 comment: for a single route→report request, little heavy compute *needs* to run in the browser — the recommendation is a server/model call. So DuckDB-WASM is a **nice-to-have**, justified only where it adds product value:

- **Optional client-side deep-dive:** once a route's Parquet slice is fetched, DuckDB-WASM lets the user *explore* all historical flights for that route (filter by hour/day/carrier) with zero extra backend cost — an engagement/analytics layer, not the core recommendation.
- **Cheap descriptive free tier:** serving pre-aggregated route stats at the edge trims backend cost for the 5-free-searches/day limited mode.
- **Verdict:** keep it as an enhancement behind the core API recommendation; **do not build the product around it or market it.** Ripple flagged to [[frontend-backend-split]] and the platform notes below.

## Where it realistically cannot win

1. **Raw accuracy vs. Google/FlightAware.** They have live ATC feeds, airline telemetry, and a global ADS-B network. We will **not** out-predict Foresight on per-flight ETA. Don't market on accuracy.
2. **Commoditized bare forecast.** A standalone "will my flight be delayed?" number is free everywhere → weak business (see [[demand-evidence]]). Our answer must be a *booking recommendation*, not a probability.
3. **Data access ceilings** (see [[regional-data-feasibility]]): no deep, clean, commercial flight-level history ≤€50/mo. Spine = free R&D history (model training) + a cheap rolling live feed (forward-growing window) → **daily forward ingestion ASAP** matters more than deep backfill.
4. **No booking/action rails.** We recommend; we don't (yet) ticket. Rebooking/compensation value accrues to players with rails (Use Case B trap in [[competitor-usecase-gap]]). The "best-for-your-buck" promise must live at the *shopping* moment, before booking.

## Strategic implication

Lead with the **best-fitting-flight-for-your-buck** recommendation as the hero (Use Case A). Reliability-aware route-shopping is the product; the lakehouse/model/edge-compute are enablers the user never has to think about. Marketing sells the **outcome (confident best-value booking)**, not transparency, not accuracy, not "edge compute."

## Handoff

- → [[staff-product-engineer]]: v1 = a **best-for-your-buck ranking** over pre-aggregated historical OTP + calibrated on-time score, weighable against price/timing; served via API (core), DuckDB-WASM as an optional edge deep-dive only. Prioritize **daily forward ingestion** over deep backfill. **Ripple:** revisit the frontend-vs-backend compute split in [[frontend-backend-split]] — DuckDB-WASM moves from load-bearing to optional.
- → [[staff-platform-engineer]]: edge-compute demotion may shrink the client-data-serving footprint — flag for the hosting/cost model (do not rewrite; your call).
- → [[marketing]]: position on **"the best-fitting flight for your buck"** (working name **FlightPal**), never on out-predicting Google or on transparency/edge-tech.

## Sources

- Cross-references [[competitors]], [[demand-evidence]], [[competitor-usecase-gap]], [[regional-data-feasibility]], [[research-summary]] (which carry the primary source URLs for competitor claims, data-source terms, and the use-case gap).
- [OpenSky FAQ — commercial use terms](https://opensky-network.org/about/faq) — accessed 2026-08-10
