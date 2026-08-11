---
type: sales
title: Unit Economics — Cost per Prediction & Gross Margin
tags: [sales, pricing, unit-economics, cost-model, deferred]
status: draft
updated: 2026-08-10
---

# Unit Economics

> **⛔ DEFERRED — NOT phase 1 (per PR #13 review).** Full margin model for the future paid tiers ([[tier-matrix]]). For the phase-1 free-limited MVP, the only cost that matters is **≤ $0.0015 per route search** (weather fetch, net of caching) → **< $0.25/free-user/mo** — see [[pricing-summary]]. **B2B dropped (B2C only).** Everything below assumes the deferred paid model. Costs tagged measured / estimated / assumed; none invented, per [[AGENTS]] rule 2.

## Cost of one Live Prediction (LP)

| Component | Cost / LP | Confidence | Basis |
|---|---|---|---|
| Fresh weather fetch (One Call 3.0) | $0.0015 *uncached* | **measured** | OpenWeather list price; 1,000 calls/day free |
| — same fetch, **amortized** across all flights at that airport×hour (cache TTL 60 min) | **~$0.0001–0.0005** | **estimated** | assumes 3–15 flights share each `(airport,hour)` pull at hubs |
| NOTAM / news signal | **~$0 (assumed)** | **assumed** | FAA NOTAM API is free-tier; **verify** licensing for commercial use |
| Model inference (GBM on CPU, FastAPI) | **~$0.00005** | **assumed** | rough; **verify** with load test — flag for [[staff-ml-engineer]] |
| Lakehouse read (Iceberg/DuckDB over SeaweedFS Parquet) | **~$0 marginal** | **estimated** | historical spine is pre-built batch; read is byte-range, not per-LP compute |
| **Blended fully-loaded cost / LP** | **~$0.0005–0.002** | **estimated** | dominated by weather fetch net of caching |

> **Point estimate used for pricing: ~$0.0015/LP** (conservative — assumes modest cache hit). Descriptive edge views (Class A) cost **~$0** and are excluded.

### Fixed / amortized infra (NOT per-LP)

- SeaweedFS storage of Parquet spine, Dagster orchestration (backfills, feature builds, batch scoring), FastAPI hosting — **fixed monthly**, amortized across all users. **Dollar figures unknown** until [[staff-platform-engineer]] sizes hosting — **flagged, do not invent.** These set the break-even user count, not the per-LP margin.

## Cost per active user / month

| Segment | Assumed LP usage | Cost / user / mo | Confidence |
|---|---|---|---|
| Free (P2/P1 trial) | 5/day cap → ~150 LP, mostly cached | **~$0.05–0.23** | **estimated** |
| Plus (P1) | ~30/day actual → ~900 LP | **~$0.45–1.35** | **estimated** |
| Pro (P1 heavy) | ~150/day → ~4,500 LP | **~$2.25–6.75** | **estimated** |
| API Premium (P4 insurer) | portfolio bursts, 100k+ LP/mo | scales linearly at blended cost | **estimated** |

## Gross margin by tier

| Tier | Revenue / mo | Est. delivery cost / mo | **Gross margin** | Note |
|---|---|---|---|---|
| **Free** | $0 (+ affiliate) | ~$0.05–0.23 | **negative by design** | Acquisition; recovered via conversion + action affiliate. Loses only *cents/user* — safe at scale because edge analytics are $0 and LP cap is bounded. |
| **Plus** ($39/yr = $3.25/mo) | $3.25 | ~$0.45–1.35 | **~58–86%** | Healthy even at worst-case usage |
| **Pro** ($59/yr = $4.92/mo) | $4.92 | ~$2.25–6.75 | **~-37% to +54%** | ⚠️ *Fair-use is load-bearing*: unbounded LP + weather cost can invert margin for a pathological scraper. Enforce the 500/day soft cap + degrade-to-cached (see [[pricing-summary]]). |
| **API Standard** ($0.006/LP, cost ~$0.0015) | usage | usage | **~75%** | Priced ~4× blended cost |
| **API Premium** ($0.003/LP volume) | usage + $1k min | usage | **~50%** | Priced ~2× cost; volume play |

## The free tier does not lose money at scale — why

- Marginal LP cost is **~$0.0015 uncached, → ~$0** on hot routes; the 5/day cap bounds worst case to **~$0.23/free-user/mo**.
- Edge descriptive analytics — the bulk of free engagement — are **$0 backend** ([[differentiation-thesis]]).
- Break-even: at Plus $39/yr, **one conversion funds ~14–70 free users' annual LP cost.** A 2–5% free→paid conversion clears the LP cost easily; the real cost gate is **fixed infra** (owned by [[staff-platform-engineer]]), not per-LP.

## The action / insurance angle (non-metered revenue)

Per [[research-summary]] finding 2, WTP attaches to the *action*. Layered on **every** tier at ~$0 delivery cost:

- **Rebooking/insurance affiliate**: hand a flagged high-risk flight to a partner (Blink-style parametric insurer, or an OTA rebook flow). Revenue = **rev-share / affiliate fee (rate unknown — negotiate; do not invent)**.
- Skews **EU** where EU261 + parametric economics are stronger and the DOT compensation rule was withdrawn ([[research-summary]] finding 5).
- This is the bridge from a commoditized forecast to monetizable action **without** us underwriting risk.

## Pricing risks (call them out)

1. **Commoditized data** — Google/airlines give the number free; consumer WTP is thin. Mitigation: don't sell the number, sell route-shopping + alerts + B2B feed ([[differentiation-thesis]]).
2. **API-cost volatility** — weather-API list prices change; our LP cost floor moves with them. Mitigation: aggressive `(airport,hour)` caching, multi-vendor abstraction (OpenWeather ↔ Tomorrow.io), degrade-to-cached.
3. **Data-access ceiling** — BTS US-only + ~3-mo lag; **OpenSky bars commercial use** ([[research-summary]] finding 4). A paid feed (Cirium/AeroAPI/commercial OpenSky) adds cost **not yet in this model** — a **gating decision** for [[staff-product-engineer]] + [[staff-platform-engineer]] that could raise the LP cost floor materially.
4. **B2B WTP unvalidated** — API prices here are estimated; **no design partner signed** ([[research-summary]] open Q2). Validate before building B2B surface.
5. **Pro fair-use inversion** — unbounded LP can go margin-negative; enforcement is mandatory, not optional.

## Handoff → [[staff-product-engineer]]

- **Hard cost ceiling per LP: $0.002.** Above it (e.g. cold route requiring a live paid-feed call), **degrade to cached base-rate** rather than serve at a loss.
- Enforce `(airport,hour)` weather cache with 60-min TTL — this is a **cost control, not just perf**.
- Full metered/gated list in [[pricing-summary]].

## Sources

- [OpenWeather One Call 3.0 — ~$0.0015/call, 1k/day free](https://openweathermap.org/api/one-call-3) — accessed 2026-08-08 *(measured)*
- [FlightAware AeroAPI — from $0.002/query, tiered mins, volume discounts](https://www.flightaware.com/commercial/aeroapi/) — accessed 2026-08-08 *(measured)*
- Cross-refs: [[metering-unit]], [[tier-matrix]], [[research-summary]], [[differentiation-thesis]], [[personas]]
