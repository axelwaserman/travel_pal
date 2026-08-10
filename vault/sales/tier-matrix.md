---
type: sales
title: Tier Matrix — Free / Plus / Pro / Team-API
tags: [sales, pricing, tiers, deferred]
status: draft
updated: 2026-08-10
---

# Tier Matrix

> **⛔ DEFERRED — NOT phase 1 (per PR #13 review).** Phase 1 ships free-limited mode only (5 route searches/day); see [[pricing-summary]]. This ladder is revisited **once MVP proves demand**. **B2B is DROPPED (B2C only)** — the Team/API column below is retained as history, not a roadmap item. Prices anchored to [[competitors]] / [[research-summary]]; personas [[personas]]; costs [[unit-economics]].

## Strategy in one line

Per [[research-summary]]: **the consumer forecast is a free/loss-leader acquisition surface; the margin is the B2B feed.** So the consumer tiers (Free/Plus/Pro) are priced to *convert and cover cost*, not to be the business — the **Team/API** tier is the real revenue engine, priced usage-based off the AeroAPI benchmark but differentiated on **transparency/calibration** ([[differentiation-thesis]]).

## The matrix

| | **Free** | **Plus** | **Pro** | **Team / API (B2B)** |
|---|---|---|---|---|
| **Price** | $0 | **$3.25/mo** ($39/yr) or $4.99 mo-to-mo | **$5.99/mo** ($59/yr) or $7.99 mo-to-mo | **Usage-based** + platform min (see below) |
| **Billing** | — | Annual (default) / monthly | Annual (default) / monthly | Monthly, metered |
| **Persona** ([[personas]]) | P2 anxious occasional; P1 trial | P1 optimizing nomad | P1 heavy / prosumer flyer | P3 TMC, P4 insurer/fintech |
| **Edge descriptive analytics** (Class A) | ✅ unlimited | ✅ unlimited | ✅ unlimited | ✅ + bulk export |
| **Live predictions (LP)** | **5/day** (~150/mo) | **50/day** (~1,500/mo) | **Unlimited, fair-use** (soft 500/day) | Metered per LP/API call |
| **Overage behavior** | **Degrade to cached base-rate** (no fresh fetch); no hard block | Degrade to cached after cap | Fair-use throttle if abused | Pay-per-use above minimum |
| **Uncertainty bands** | ✅ (trust-building, cheap) | ✅ | ✅ | ✅ + Brier/reliability metadata |
| **Route-shopping analytics** (carrier×time reliability) | Basic (current cut) | ✅ full depth | ✅ full + compare | ✅ via API |
| **Historical depth** | 3 months | 12 months | Full spine | Full + backtests |
| **Proactive delay alerts** (≥3–6h lead) | ❌ | ✅ up to 5 watched flights | ✅ unlimited watchlist | ✅ webhooks/push feed |
| **Multi-trip / itinerary risk** | ❌ | ✅ | ✅ | ✅ portfolio scoring |
| **API access** | ❌ | ❌ | ❌ (read-only export only) | ✅ REST + batch |
| **SLA / support** | community | email | priority email | **contractual SLA**, calibration report, design-partner support |
| **Action handoff** (insurance/rebook affiliate) | ✅ (monetized via partner, see [[unit-economics]]) | ✅ | ✅ | white-label option |

## Price anchoring (all competitor prices *measured*, from [[competitors]])

- **Flighty Pro = $59.99/yr** is the proven B2C ceiling for delay foresight. We set **Pro at $59/yr — at the ceiling but differentiated on route-shopping + transparency**, not undercutting on a commodity number we can't out-predict ([[differentiation-thesis]] §"cannot win").
- **Plus at $39/yr** deliberately undercuts Flighty by ~35% to win the price-sensitive P1 who won't pay $60 for a tracker, monetizing route analytics + alerts instead.
- **AirHelp+ €36–€90/yr / 35% contingency; Compensair 25%** → the *action* is worth more than the forecast. We don't compete here; we **hand off to a partner** and take affiliate/rev-share (see [[unit-economics]] "action angle").
- **AeroAPI = from $0.002/query, tiers at $0 / $100-min / $1,000-min per month, volume discounts to 94% off above $64k/mo** → our **Team/API** benchmark.

## Team / API tier detail (the margin story)

Usage-based, mirroring the AeroAPI structure but positioned on **auditable methodology** (the B2B wedge from [[personas]] P3/P4):

| Sub-tier | Platform min / mo | Per-LP list price | Rate limit | Target |
|---|---|---|---|---|
| **Team (seat floor)** | $99/mo (up to 5 seats) | included quota 5k LP, then $0.006 | 5 req/s | Small TMC / duty-of-care |
| **API Standard** | $100/mo min | **$0.006/LP** (est., ~3× blended cost) | 10 req/s | Fintech / mid TMC |
| **API Premium** | $1,000/mo min | **$0.003/LP** volume (est.) | 100 req/s | Insurer portfolio scoring (P4) |

> Per-LP prices are **estimated** (priced at ~2–4× blended marginal cost from [[unit-economics]]); the platform minimums are **assumed**, benchmarked to AeroAPI's $100/$1,000 structure. **Validate against a design partner before publishing** (open question in [[research-summary]]).

## Packaging levers

- **Annual default** (monthly at a premium) — smooths the recurring weather-API cost and improves retention.
- **Action affiliate** across all tiers: rebook/insurance handoff (Hopper/Blink-style partner) → revenue with ~$0 delivery cost; skews EU where EU261 economics are stronger ([[research-summary]] finding 5).
- **B2B lands usage-based, not seat-based** — insurers/TMCs score in bursts.

## Handoffs

- → [[marketing]]: tier names, price points ($0 / $39 / $59 / usage), value props per persona above.
- → [[staff-product-engineer]]: the caps in this table become the enforced quotas — see [[pricing-summary]] gating list and [[unit-economics]] cost ceilings.

## Sources

- [Flighty pricing $59.99/yr, $299 lifetime](https://flighty.com/pricing) — accessed 2026-08-08 *(measured)*
- [AeroAPI pricing tiers & volume discount](https://www.flightaware.com/commercial/aeroapi/) — accessed 2026-08-08 *(measured)*
- [AirHelp+ €36–€90/yr](https://travel-dealz.com/deal/airhelp-plus/) — accessed 2026-08-08 *(measured)*
- Cross-refs: [[competitors]], [[personas]], [[research-summary]], [[differentiation-thesis]], [[metering-unit]], [[unit-economics]]
