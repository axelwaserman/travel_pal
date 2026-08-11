---
type: research
title: Research Summary & Go/No-Go — Flight Delay Prediction
tags: [product, research, summary, moc]
status: draft
updated: 2026-08-08
---

# Research Summary & Go/No-Go

> One-page synthesis of [[competitors]], [[demand-evidence]], [[personas]], [[differentiation-thesis]]. Handoffs to [[sales]] and [[staff-product-engineer]] at the end.

## Lean: **Conditional Go — pivot the business model, not the tech**

The pain is real and recurring (~1 in 4–5 US flights disrupted; ~$500 avg. traveler cost — *estimated*), and people demonstrably pay for delay foresight (Flighty $59.99/yr) and for disruption *action* (AirHelp 35%, parametric insurers). **But the standalone "will my flight be delayed?" forecast is already commoditized to $0** by Google Flights and airline apps, and out-predicting **FlightAware Foresight** on raw accuracy is not realistic. So: **do not build TravelPal as a standalone consumer delay-forecast app.** Build it where the lakehouse actually wins — **transparent route/carrier reliability analytics (free, edge-served) as an acquisition wedge, monetized via a B2B methodology/feed (insurers, TMCs) and/or an action partnership (rebook/insure).**

## Five findings

1. **Prediction is commoditized at the consumer edge.** Google (free, in-path, confidence-gated), airline apps, and free clones (DelayGuard.ai) give the number away. Weak standalone B2C WTP.
2. **Money is in action + B2B, not the number.** Flighty (sub), Hopper (rebook), AirHelp/Compensair (compensation), Blink (parametric payouts), Cirium/FlightAware (data feeds) all monetize the *consequence* or the *feed*.
3. **Our defensible edge is cost + transparency + route-shopping**, not accuracy (see [[differentiation-thesis]]). Edge DuckDB-WASM = genuinely-free descriptive tier; auditable methodology = a B2B selling point.
4. **Data access is the hard constraint.** BTS = US-only, lags **up to ~3 months** (stale spine); OpenSky **prohibits commercial use** without a paid license and thins outside EU/US. Fresh/global/commercial requires budgeted paid feeds — a gating decision for eng + sales.
5. **Regulatory tailwind is soft in the US.** The DOT cash-compensation rule was **withdrawn 2025-11-17**; the US has automatic *refunds* (3h dom / 6h intl) but no EU261-style fixed payout. So a US "get compensated" hook is weaker than in the EU — favors the EU market for any compensation/insurance angle.

## Evidence-quality flags

- **Do not reuse** the viral "Google Flights = 89.3% accuracy / MIT Lincoln Lab / 28 carrier APIs / 7.2B records" stats — they trace to AI-content-farm SEO pages, no primary source. Likely **fabricated**.
- Market-size figures ($1.38B→$4.03B apps; $4.8B→$11.2B disruption mgmt) are **report-mill estimates** — directional only.
- Flighty ">95% accurate" is **vendor marketing**, unverified.

## Handoff → [[sales]]

- **Personas & WTP:** anchor B2C freemium below Flighty's **$59.99/yr** ceiling; the real margin candidate is the **B2B feed** (P3 TMCs, P4 insurers — see [[personas]]).
- **Competitor pricing captured:** Flighty $59.99/yr ($299 lifetime); AirHelp 35% + AirHelp+ €36–€90/yr; Compensair 25%; parametric = B2B white-label. Use for tier/undercut modeling.
- **Model the free tier's true cost** — the edge-served descriptive tier is the acquisition engine; paid = alerts + route analytics + API.

## Handoff → [[staff-product-engineer]]

- **Required output contract:** calibrated `P(delay)` and `P(delay ≥ Xh)` + expected delay-minutes **with confidence bands**; calibration/auditability > raw accuracy (B2B buyers demand it).
- **Lead time that matters:** day-of forecasts need **≥3–6h** lead to enable proactive rebooking; booking-time needs route/carrier base rates.
- **Data-source constraints are binding:** BTS US-only + ~3-month lag; OpenSky non-commercial only. Decide early: accept US-historical MVP scope, or budget paid feeds (Cirium/FlightAware AeroAPI/commercial OpenSky) for freshness/global. This shapes the whole ingestion design.
- **Design for the feed, not just the app:** the B2B API is the likely revenue path — treat it as a first-class product surface.

## Open questions

1. Can we secure a **paid/commercial data feed** within budget, or is the MVP locked to stale US BTS historicals? (Blocks freshness claims.) `#task/product ⛓ [[staff-product-engineer]]`
2. Is there a **design partner** (insurer via Blink-style infra, or a TMC) willing to pay for a calibrated feed? Validates the B2B thesis before consumer build. `#task/sales`
3. What **calibration bar** do B2B buyers actually require (Brier/reliability), and can our lakehouse+ML hit it vs. Foresight? `#task/ml ⛓ [[staff-ml-engineer]]`
4. Raw-quote demand corpus (Reddit/app reviews) still owed — 30–50 verbatim pains to harden [[demand-evidence]]. `#task/product`
5. EU vs US launch market, given the DOT compensation-rule withdrawal favors EU261 economics. `#task/marketing`

## Follow-up: EU data feasibility & regional monetization (2026-08-09)

See [[regional-data-feasibility]]. **A commercial-safe, deep, flight-level EU historical spine ≤€50/mo does not exist** — Eurocontrol CODA is non-commercial, ADRR is R&D-only (2-yr/4-month latency), OAG/Cirium are enterprise-priced; only shallow commercial APIs (AeroDataBox ~€5–30/mo, aviationstack ~€50/mo) fit budget. **Recommended v1: EU/UK on the EU261/UK261 monetization hook, hybrid spine = ADRR (free, model training) + AeroDataBox (commercial live, forward-growing window).** Monetization confirmed EU/UK-strongest for the *action/insurance* layer; US is refunds-only/commoditized (consumer-subscription only). → [[staff-product-engineer]]: build for a rolling forward spine, not deep backfill; ≤€50/mo is a hard feed constraint. → [[sales]]: model action/B2B tiers around EU261.

## Follow-up: B2C use-case gap analysis (2026-08-10)

See [[competitor-usecase-gap]]. Three consumer jobs assessed: **(A) pre-booking reliability shopping = GAP** (no one offers sortable, calibrated, multi-criteria reliability shopping; Google only flashes a binary "often delayed" flag) — **best fit for our wedge + cheapest to serve (batch analytics, no booking rails/live feed)**; **(C) day-of foresight = PARTIAL** (Flighty already owns and monetizes it; only unmet micro-gap = integrated "leave-by" + cross-platform; needs costlier live feeds) → Phase-2 companion; **(B) disruption rebooking = TRAP** (solved by airlines/OTAs/Capital One with booking rails we lack; our transparency wedge adds nothing post-cancellation). **Recommendation: anchor MVP on Use Case A — reliability route-shopping.** → [[staff-product-engineer]]: v1 = calibrated on-time-probability ranking/scoring over pre-aggregated historical OTP, sortable vs price/timing; batch-first, no live-booking integration. (App in the Air defunct 2024-10; Freebird → Capital One.)

## Sources

Primary source URLs live in the linked notes: [[competitors]], [[demand-evidence]], [[differentiation-thesis]], [[regional-data-feasibility]], [[competitor-usecase-gap]]. Key additions cited here:

- [DOT withdraws proposed passenger-compensation rulemaking (2025-11-17) — Eckert Seamans](https://www.eckertseamans.com/stay-informed/blogs/aviation/dot-withdraws-proposed-airline-passenger-rights-rulemaking) — accessed 2026-08-08
- [US DOT automatic refund rule — TravelStacks](https://www.travelstacks.com/blog/us-dot-automatic-refund-rule-full-breakdown) — accessed 2026-08-08
- [OpenSky FAQ (commercial-use terms)](https://opensky-network.org/about/faq) — accessed 2026-08-08
- [BTS](https://www.bts.gov/) (on-time data timeliness, up-to-3-month lag) — accessed 2026-08-08
- [PIRG Plane Truth 2026](https://pirg.org/edfund/resources/plane-truth-2026/) — accessed 2026-08-08
