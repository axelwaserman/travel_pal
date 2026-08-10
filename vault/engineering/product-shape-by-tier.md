---
type: engineering
title: Product Shape by Tier
tags: [engineering, product, tiers, metering, gating, b2c]
status: draft
updated: 2026-08-10
---

# Product Shape by Tier

> What each surface gives and how gating is enforced. **B2C only — B2B is dead.** **MVP = limited mode (5 free route searches/day); full pricing is NOT in phase 1.** Consumes [[frontend-backend-split]], [[serving-service]]. See [[architecture-summary]].

> [!note] Locked in PR #13
> B2C only. Working name **FlightPal**. Positioning = **"guarantee the best-fitting flight for your buck."** MVP ships **limited mode** (5 free searches/day) — later paid tiers are sketched below but **deferred past phase 1**.

## Phase 1 (MVP) — limited mode only

| Surface | Data source | Gating |
|---|---|---|
| Route/carrier reliability, cancellation rates, hour×DOW heatmap ("best-fitting flight for your buck") | **Edge** public Parquet + DuckDB-WASM (*nice-to-have* — server-rendered fallback fine) | none (public, ~$0) |
| **Live per-flight prediction** (`P(delay≥Xh)` + bands + reason codes) | **API** `/v1/predict` ([[serving-service]]) | **5 free route searches/day** via Redis token-bucket keyed on device/session id → then a friendly upsell wall |

- No login required in MVP; the daily cap is device/session-scoped.
- No paid plan, no billing integration in phase 1 — the wall exists to prove demand + protect cost, not to charge yet.

## Later phases (sketch — NOT phase 1)

All B2C. Names/prices provisional, pending validation:

| Tier | Gets | Enforcement |
|---|---|---|
| **Free** | Route-shopping + capped daily predictions (the MVP surface) | device-id daily cap |
| **Plus** (B2C sub) | Uncapped predictions, day-of alerts (≥3–6h lead), multi-flight watchlist | account + API key, higher quota |

Anchor Plus **below Flighty's $59.99/yr** ([[research-summary]]). No API/feed tier — **B2B is out of scope entirely.**

## The gating mechanic (single rule)

- **Edge = public, ungated.** Aggregate, public-domain-derived route stats live in a public bucket (DuckDB-WASM reads them, or a server fallback). Nothing sensitive, nothing metered — so ~$0 to serve.
- **Predictions = metered API.** Every `/v1/predict` passes the [[serving-service]] rate-limiter (device-id token bucket, 5/day in MVP). Fresh signals + inference never touch the public bucket, so they can't leak to the free edge ([[frontend-backend-split]]).
- Boundary enforced by **where data physically lives**, not client-side checks.

## Strategic alignment

- The edge route-shopping surface = the **acquisition wedge**: cheap-to-serve, answers "best-fitting flight for your buck."
- Live prediction is the **hook behind the 5/day wall** — proves willingness to engage before we build billing.
- **DuckDB-WASM is a nice-to-have**, not the core feature; the core is the best-fit answer, however rendered.

## Open questions
- [ ] Confirm the exact free cap (5/day) + upsell copy with [[marketing]]. `#task/product ⛓ [[marketing]]`
- [ ] Does Free expose forward-looking base rates, or only backward-looking history? `#task/product`
- [ ] When (which phase) does Plus + billing land? `#task/product 🔽`

## Sources
- [[research-summary]], [[personas]] (repo vault) — accessed 2026-08-10
- [Flighty pricing](https://flighty.com/pricing) (anchor for a later Plus tier) — accessed 2026-08-10
