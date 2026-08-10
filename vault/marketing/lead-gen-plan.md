---
type: marketing
title: Lead-Generation Plan — Funnel, Surfaces & Channels
tags: [marketing, gtm, lead-gen, funnel]
status: draft
updated: 2026-08-10
---

# Lead-Generation Plan

> **Rev. per PR #13.** **B2C-only** (B2B outbound dropped). Working name **FlightPal** ([[naming]]). Adds a **Chrome-extension** surface and an **aircraft/cabin** hook. MVP = **limited mode, 5 free searches/day**. Funnels into [[sales]] consumer tiers ([[tier-matrix]]) via the outcome-led [[positioning]].

## Funnel with one measurable goal per stage

| Stage | Definition | Primary lever | Measurable goal (**assumed** targets — calibrate after 60 days) |
|-------|-----------|---------------|------------------------------------------------------------------|
| **Awareness** | Sees FlightPal (SEO page, extension listing, forum, social) | Public route-reliability pages + Chrome extension + community | 50k monthly organic sessions |
| **Signup (free)** | Creates a free account (limited mode, 5 searches/day) | "Find my best flight" CTA | 3–5% visitor→signup |
| **Activation** | Runs first best-flight search / sets first alert | Onboarding to 1 route compare + 1 watched flight | 40% of signups activate in 7 days |
| **Upgrade** | Converts Free→Plus/Pro | 5-searches/day cap prompts; alert + aircraft-depth gates | 2–5% free→paid |

## Surfaces

### 1. Chrome extension (NEW — review lead-gen:36) — flagship consumer surface
A browser extension layered on top of web + mobile that **grades each flight option inline** while the user shops on Google Flights / an OTA:
- **Grade = historical timeliness + airline rating + specific aircraft** (is the assigned tail a recently renovated cabin?) + **connection-safety** for multi-leg itineraries.
- Meets the user at the **exact booking moment** — highest-intent placement, no app switch.
- Distribution: Chrome Web Store listing (ASO), demo GIF for social/PR, "grade your flight" hook.
- Goal: 10k installs in 6 months; extension→signup 15%.

### 2. Public route-reliability pages (SEO)
Free pages showing most/least reliable routes, carriers, best times, and aircraft/cabin notes.
- **Engine note:** DuckDB-WASM edge rendering is now a **nice-to-have** (per team context), not a dependency — pages can ship server-rendered first, edge-optimized later. Keep the SEO/PR value regardless of rendering path.
- **PR/link-bait:** periodic "most/least reliable routes & worst hub-hours" data story → backlinks + press (the AirHelp/PIRG "worst airports" genre already earns coverage, [[demand-evidence]]).
- Goal: page-1 for 100 route/airport long-tails in 6 months.

### 3. Mobile + web app
The core product; free limited mode is the hook, alerts/aircraft depth are the upgrade.

## Channels (ranked by cost-efficiency, all B2C)

### SEO — primary engine (P1/P2)
- Target **long-tail decision intent**: `is flight [X] delayed`, `will my flight be late`, `most reliable airline [route]`, `best time to fly [route]`, `[airport] delay statistics`, `which plane [route]`.
- Rationale: head terms ("flights" ~13.6M/mo, "google flights" ~45.5M/mo — **measured**, third-party) are unwinnable; **long-tail decision queries are low-competition, high-intent** (travel-SEO consensus).
- Goal: rank page-1 for 100 long-tails in 6 months.

### Community / forums (P1 + P2)
- **Reddit** (r/travel, r/delta, r/unitedairlines, r/awardtravel), **FlyerTalk**, travel Discords.
- Play: genuinely useful answers with a route/aircraft data snippet + link; seed the "most reliable route" and "worst cabins on route X" data stories. Never spam.
- Goal: 20 high-value posts/mo; track referral signups.

### App-store / Chrome-store ASO (P2 volume)
- ASO on "flight delay predictor / best flight picker" + the extension listing. Free tier is the hook.
- Goal: secondary to web+extension until the web funnel is proven.

> **Dropped:** B2B LinkedIn/outbound + design-partner pipeline (B2B feed cut, PR #13). All spend now consumer-side.

## Attribution & measurement (handoff to [[staff-product-engineer]])

- First-party, privacy-respecting analytics (respect `rules/web/security.md` CSP; no invasive third-party trackers).
- UTM taxonomy per channel + extension source; map free→paid to acquisition source.
- Instrument the **activation event** (first best-flight search / first alert) — the funnel's leading indicator.

## Budget posture

- **Near-zero paid spend to start:** SEO + Chrome extension + community compound for free. Reserve paid search only to defend branded terms once the name clears ([[naming]]).

## Handoff

- → [[staff-product-engineer]]: Chrome-extension grading surface (inline on OTA/Google Flights); public route pages (server-render first, DuckDB-WASM edge optional); analytics/attribution + activation instrumentation; free-limited-mode (5/day) signup flow; **tail-assignment** data for the cabin grade.
- → [[brand-system]]: extension + landing + route-page visual direction.

## Sources

- [Travel SEO keyword volumes — Clicks.so](https://resources.clicks.so/popular-keywords/travel-keywords) · [Flights keyword volumes — kwrds.ai](https://www.kwrds.ai/top-keywords/flights) — accessed 2026-08-10 *(measured, third-party estimates)*
- [Travel SEO long-tail strategy — LowFruits](https://lowfruits.io/blog/travel-seo-keywords/) — accessed 2026-08-10
- Community/PR genre + WTP evidence: [[demand-evidence]] (primary URLs there) — accessed 2026-08-10
- Cross-refs: [[personas]], [[tier-matrix]], [[differentiation-thesis]], [[positioning]]
