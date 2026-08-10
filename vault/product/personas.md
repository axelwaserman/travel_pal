---
type: research
title: Personas & JTBD — Flight Delay Prediction
tags: [product, research, personas, jtbd]
status: draft
updated: 2026-08-08
---

# Personas & JTBD — Flight Delay Prediction

> Who acts on a delay prediction, at what trigger, and what accuracy/lead-time makes it useful. See [[demand-evidence]], [[competitors]], [[differentiation-thesis]].

The legacy "**Optimizing Nomad**" (see `tech_product_Architecture.txt` §1.2) is directionally right but too narrow and too *retrospective* ("analyze your past"). The reframe is **predictive + forward-looking**, so personas are organized by **the decision the prediction changes**.

## P1 — The Optimizing Nomad (revised, B2C anchor)

- **Who:** high-frequency business/semi-pro flyers (consultants, engineers, creators). High data literacy, reject generic advice, treat transit as billable.
- **JTBD:** *"When I'm booking or mid-trip, help me choose the route/carrier/time least likely to burn my day."*
- **Trigger:** (a) booking a flexible itinerary; (b) day-of, watching an at-risk connection.
- **Decision:** pick carrier/time at booking; rebook proactively day-of.
- **Useful threshold:** route/carrier-level historical reliability at booking; day-of P(delay) with **≥3–6h lead time** and a *reason* (late aircraft / ATC / weather). Calibration matters more than raw accuracy — a trustworthy 70% that's well-calibrated beats an opaque "95%".
- **Reality check:** this persona is exactly who **Flighty already monetizes**. We must beat Flighty on *route-shopping analytics* (our lakehouse edge), not on personal tracking.

## P2 — The Anxious Occasional Flyer (B2C volume)

- **Who:** 2–6 flights/yr, low tolerance for uncertainty, price-sensitive.
- **JTBD:** *"Tell me plainly if I should worry, and what to do about it."*
- **Trigger:** the days before a trip; airport morning-of.
- **Decision:** buy insurance? leave earlier? pick refundable fare?
- **Useful threshold:** simple, reassuring, explained probability. **Free-tier territory** — hard to monetize directly; monetize via insurance/affiliate handoff.
- **Reality check:** Google Flights + airline app already serve this for $0. Weak standalone WTP.

## P3 — Corporate Travel Manager / TMC (B2B — strongest WTP)

- **Who:** travel managers, TMCs, duty-of-care teams booking for many employees.
- **JTBD:** *"Minimize disruption cost and duty-of-care exposure across a portfolio of trips."*
- **Trigger:** policy config, booking approval, proactive traveler re-accommodation.
- **Decision:** steer bookings to reliable routes; pre-position rebooking.
- **Useful threshold:** route/carrier reliability + forward risk as an **API/feed**, SLA-backed. 80% of business travelers report disruption (see [[demand-evidence]]) → concrete pain with a budget.
- **Reality check:** Cirium/FlightAware already sell here; entry needs a price/UX wedge (cheap DuckDB-edge analytics, transparent methodology).

## P4 — Parametric Insurer / Fintech (B2B — data buyer)

- **Who:** insurers (via Blink-style infra), OTAs, fintechs offering rebook guarantees.
- **JTBD:** *"Price and trigger flight-delay risk accurately and cheaply."*
- **Trigger:** underwriting a policy; firing an automated payout.
- **Decision:** premium pricing, trigger thresholds, reserve modeling.
- **Useful threshold:** calibrated P(delay ≥ Xh) per flight, backtested, with confidence bands. This is where a **lakehouse + ML methodology sells itself** — buyers care about calibration and auditability, not UX.

## Segmentation takeaway

| | B2C forecast standalone | B2C action (rebook/insure) | B2B feed/analytics |
|--|--|--|--|
| Demand | Real but **commoditized (free)** | Real, monetized by others | Real, budgeted |
| Our edge | Route analytics only | Needs partner (insurer/OTA) | **Lakehouse methodology** |
| Verdict | Loss-leader / free tier | Partner play | **Most defensible** |

## Handoff to [[sales]]

- Price the **B2C** as freemium (free forecast, paid route-analytics + alerts) — anchor near Flighty's $59.99/yr ceiling, undercut or differentiate on route-shopping.
- The **B2B feed (P3/P4)** is the likelier margin story — validate WTP before over-investing in consumer UX.

## Sources

- `tech_product_Architecture.txt` §1.2 (legacy persona) — repo, accessed 2026-08-08
- [Half of passengers still face disruptions in 2025 — thetraveler.org](https://www.thetraveler.org/half-of-airline-passengers-still-face-disruptions-in-2025/) — accessed 2026-08-08
- [Flighty pricing](https://flighty.com/pricing) — accessed 2026-08-08
- (Cross-refs: [[competitors]], [[demand-evidence]])
