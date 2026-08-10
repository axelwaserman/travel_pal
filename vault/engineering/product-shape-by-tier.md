---
type: engineering
title: Product Shape by Tier
tags: [engineering, product, tiers, metering, gating]
status: draft
updated: 2026-08-08
---

# Product Shape by Tier

> What each tier gets and how gating is enforced technically. Consumes [[frontend-backend-split]], [[serving-service]]. ⛓ **[[sales]] / [[tier-matrix]] not yet written** — tier names/quotas below are **assumed** and must be reconciled with [[sales]]. See [[architecture-summary]].

> [!warning] Assumed input
> No `vault/sales/` note exists at time of writing. The tier taxonomy (Free/Plus/Pro/API) is inferred from [[research-summary]] handoff (freemium anchored below Flighty $59.99/yr; B2B feed as margin story) and [[personas]] P1–P4. **Confirm with [[sales]] before build.**

## Tier → surface → enforcement

| Tier | Persona | Surfaces | Data source | Enforcement |
|---|---|---|---|---|
| **Free** | P2 anxious flyer, top-of-funnel | Route/carrier reliability, cancellation rates, hour×DOW heatmap, **base-rate "typically X% on-time"** | **Edge**: public Parquet + DuckDB-WASM | None needed — anonymous public bucket ([[frontend-backend-split]]); ~$0 marginal cost |
| **Plus** (B2C sub, < $59.99/yr) | P1 optimizing nomad | Everything in Free **+ live per-flight prediction**, day-of alerts (≥3–6h lead), calibrated bands + reason codes | **API** `/v1/predict`, `/v1/alerts` | API key → tier; Redis token bucket (soft monthly quota) |
| **Pro** (B2C power) | P1 heavy | Higher quota, multi-flight watchlist, CSV/export, historical drill-down | API + edge | Higher quota bucket; export gated by tier |
| **API / B2B** | P3 TMC, P4 insurer | Metered calibrated **feed**, `/v1/predict/batch`, SLA, `/v1/methodology` backtest + calibration docs, snapshot-pinned responses | API (contractual) | Per-key quota + SLA tier; usage billing on metering unit |

## The gating mechanics (single rule)

- **Free = edge-only.** Free users are never issued an API key; they get the static public Parquet surfaces. No server compute, so nothing to meter — and nothing sensitive is exposed (aggregate, public-domain BTS).
- **Paid = API key + metered.** Every prediction/alert/feed call passes the [[serving-service]] rate-limiter keyed to the tier. The metering unit (assumed = one prediction) and quotas come from [[sales]]/[[unit-economics]].
- Boundary is enforced by *where the data physically lives*, not by client-side checks: fresh signals + predictions never touch `frontend-exports`, so they cannot leak to the free edge ([[frontend-backend-split]]).

## Strategic alignment ([[differentiation-thesis]])

- Free edge tier = the **acquisition wedge** (transparent route-shopping at ~$0 to serve) — the thing incumbents give away as a black box or price for enterprises.
- **API/B2B is the margin story** ([[personas]] P3/P4) — calibrated + auditable feed. Treated as a first-class product surface, not an afterthought.
- Consumer prediction (Plus/Pro) is a *modest* sub, not the core bet — raw forecast is commoditized ([[research-summary]]).

## Open questions
- [ ] **[[sales]] must publish [[tier-matrix]] + [[unit-economics]]**: confirm tier names, price points, metering unit, quotas. `#task/eng 🔺 ⛓ [[sales]]`
- [ ] Does Free expose *any* forward-looking base-rate, or only backward-looking history? (Affects how much value is free.) `#task/product ⛓ [[marketing]]`
- [ ] EU vs US launch (DOT compensation-rule withdrawal favors EU261) shapes which tier leads GTM. `#task/marketing`

## Sources
- [[research-summary]], [[personas]], [[differentiation-thesis]] (repo vault) — accessed 2026-08-08
- [Flighty pricing](https://flighty.com/pricing) (anchor) — accessed 2026-08-08
