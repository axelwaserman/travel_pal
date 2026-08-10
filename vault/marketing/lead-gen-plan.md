---
type: marketing
title: Lead-Generation Plan — Funnel & Channels
tags: [marketing, gtm, lead-gen, funnel]
status: draft
updated: 2026-08-08
---

# Lead-Generation Plan

> Low-budget acquisition matched to where [[personas]] actually are. Funnels into [[sales]] tiers ([[tier-matrix]]) via the [[positioning]] wedge. Working name **Glasswing** ([[naming]]).

## Funnel with one measurable goal per stage

| Stage | Definition | Primary lever | Measurable goal (initial targets — **assumed**, calibrate after 60 days) |
|-------|-----------|---------------|--------------------------------------------------------------------------|
| **Awareness** | Sees Glasswing (SEO page, forum reply, social) | Public delay-stats page + SEO + community | 50k monthly organic sessions to the stats page |
| **Signup (free)** | Creates a free account | "Get alerts on this route" CTA on stats page | 3–5% visitor→signup |
| **Activation** | Runs first live prediction / sets first alert | Onboarding to 1 watched flight + 1 route compare | 40% of signups activate in 7 days |
| **Upgrade** | Converts Free→Plus/Pro, or books a B2B call | Alert-cap prompts; route-analytics depth gate | 2–5% free→paid (matches [[unit-economics]] break-even); 10 qualified B2B convos/qtr |

> Conversion economics (one Plus conversion funds ~14–70 free users' LP cost) come from [[unit-economics]] — the free tier is affordable *because* edge analytics are ~$0.

## The flagship top-of-funnel asset: a public delay-stats page

**"Glasswing Delay Almanac"** — a free, SEO-optimized public page powered by the **existing DuckDB-WASM + Parquet edge dashboards** (Class A, ~$0 to serve, [[metering-unit]]). This *is* the transparency wedge made visible and the cheapest scalable acquisition surface we have.

- **Content:** most/least reliable routes & carriers, on-time distributions, "worst hub-hours," seasonal patterns — all client-rendered at the edge.
- **SEO surface:** programmatic pages per route/airport/carrier targeting long-tail intent (see below).
- **Conversion hook:** every page ends with *"Get told before the airline does → free alerts on this route."*
- **PR/link-bait:** a periodic "most/least reliable routes" data story → earns backlinks + press (the AirHelp/PIRG "worst airports" genre already gets coverage — [[demand-evidence]]).

## Channel plan (ranked by cost-efficiency)

### 1. SEO — the primary engine (P1/P2)
- Target **long-tail informational intent**: `is flight [X] delayed`, `will my flight be late`, `most reliable airline [route]`, `best time to fly [route] to avoid delays`, `[airport] delay statistics`.
- Rationale: broad head terms ("flights" ~13.6M/mo, "google flights" ~45.5M/mo — **measured**, third-party) are unwinnable & owned by Google; **long-tail decision queries are low-competition and high-intent** (travel SEO consensus). The stats page's programmatic route/airport pages are purpose-built for this.
- Goal: rank page-1 for 100 route/airport long-tails in 6 months.

### 2. Community / forums (P1 anxious + nomad)
- **Reddit** (r/travel, r/delta, r/unitedairlines, r/awardtravel, r/flighty), **FlyerTalk**, frequent-flyer Discords/Slacks.
- Play: **genuinely useful answers** with a route-reliability data snippet (link to the relevant Almanac page), never spam. Seed the "most reliable route" data stories here.
- Goal: 20 high-value posts/mo; track referral signups.

### 3. B2B outbound + content (P3 TMC / P4 insurer — the margin)
- **LinkedIn + X** thought-leadership on *auditable/calibrated* flight-risk ("why black-box delay models are an underwriting liability"). Aligns with the transparency wedge B2B buyers reward.
- **Warm outbound** to TMCs & parametric insurers (Blink-style ecosystem) for the design-partner ask (open Q in [[research-summary]]; sales owns the close, [[pricing-summary]]).
- Goal: 10 qualified B2B conversations/quarter; 1 design partner signed (feeds [[sales]]).

### 4. App-store presence (P2 volume)
- ASO on "flight delay predictor / tracker" once mobile ships; the free tier is the hook.
- Goal: secondary to web until web funnel proven.

## Attribution & measurement (handoff to [[staff-product-engineer]])

- Privacy-respecting analytics on the stats page + signup funnel (respect `rules/web/security.md` CSP; no invasive third-party trackers — favors self-hosted/first-party analytics).
- UTM taxonomy per channel; map free→paid conversion to acquisition source.
- Instrument the **activation event** (first LP / first alert set) explicitly — it's the funnel's leading indicator.

## Budget posture

- **Near-zero paid spend to start.** Lean on SEO + the free edge-served stats page + community — this compounds and matches the cost-structure advantage in [[differentiation-thesis]]. Reserve paid search only to defend branded terms once the name is set ([[naming]]).

## Handoff

- → [[staff-product-engineer]]: public stats page = programmatic SEO route/airport pages on DuckDB-WASM edge; analytics/attribution + activation instrumentation; free-alert signup flow.
- → [[sales]]: B2B design-partner pipeline feeds the Team/API validation ([[pricing-summary]] open questions).
- → [[brand-system]]: stats-page + landing visual direction.

## Sources

- [Travel SEO keywords — search volume/difficulty (Clicks.so)](https://resources.clicks.so/popular-keywords/travel-keywords) · [Flights keyword volumes — kwrds.ai](https://www.kwrds.ai/top-keywords/flights) — accessed 2026-08-08 *(measured, third-party estimates)*
- [Travel SEO long-tail strategy — LowFruits](https://lowfruits.io/blog/travel-seo-keywords/) · [Aviation SEO methodology — Off The Ground](https://www.offthegroundmarketing.com/blog/aviation-seo-keyword-research-guide) — accessed 2026-08-08
- [B2B flight-risk positioning — VariFlight DataWorks](https://dataworks.variflight.com/blog/predicting-delays-with-incoming-flights-for-otas-tmcs-and-insurance/) — accessed 2026-08-08
- Community/PR genre + WTP evidence: [[demand-evidence]] (primary URLs there) — accessed 2026-08-08
- Cross-refs: [[personas]], [[tier-matrix]], [[unit-economics]], [[differentiation-thesis]], [[metering-unit]]
