---
type: sales
title: Pricing Summary & Handoff — FlightPal Monetization
tags: [sales, pricing, summary, moc, handoff]
status: draft
updated: 2026-08-10
---

# Pricing Summary & Handoff

> **PHASE 1 SCOPE (per PR #13 review): free-limited mode ONLY — no paid tiers, no B2B.** This note now defines just the MVP metering (a **route search** + a **5/day free cap**). The full tier ladder and unit economics are preserved but **descoped to a later phase** — see the appendix and [[tier-matrix]] / [[unit-economics]] (both marked DEFERRED). Grounded in [[research-summary]], [[competitors]], [[personas]], [[differentiation-thesis]].

## Phase-1 recommendation in three sentences

Ship a working MVP that is **free with a hard daily limit** — a user gets **5 route searches per day**, then is capped. Meter only that one unit; don't build billing, paid tiers, or an API yet. Prove interest first; **defer all monetization** ([[tier-matrix]], [[unit-economics]]) until usage justifies it.

## MVP metering unit: **1 route search**

> **1 route search = one user-initiated query for the delay/reliability outlook of a route** — `origin → destination`, optionally `+ date` and/or `+ carrier` — returning the risk read (base-rate reliability, and where available a fresh-signal-adjusted outlook).

Rules so the cap is unambiguous for [[staff-product-engineer]]:

- **The metered action is the search submit**, not scrolling/re-rendering an already-returned result.
- **Re-opening the same result within a session (no re-query) = 0** — cache the last result client-side.
- **Changing origin/dest/date/carrier and re-submitting = 1** new route search.
- Counts reset on a **rolling 24h** (or calendar-day UTC — [[staff-product-engineer]]'s call; state the choice in UI).

## Free-limited cap: **5 route searches / day / user**

- **Justification:** demonstrates the core value (transparent route-shopping, the [[differentiation-thesis]] wedge) while capping cost and blocking scraping. 5/day covers a real trip-planning session; heavy/repeat use hits the wall and signals latent demand we can later monetize.
- **Overage behavior:** **block with an upgrade-intent prompt** ("You've used your 5 free searches today — [notify me when paid plans launch]"). This doubles as a **demand-capture signal** for the deferred paid phase. No silent failure.
- **Cost note:** if a route search triggers a fresh weather fetch, cost is **~$0.0015 (measured OpenWeather)** worst case, near-$0 with airport×hour caching; 5/day bounds a free user to **< $0.25/mo** ([[unit-economics]]). Safe at scale.

## Handoff → [[staff-product-engineer]]: phase-1 metering (only this)

**Meter:** per-user route-search count, keyed to `(user_or_device, rolling-24h)`; the search-submit event is the increment.

**Rate-limit / enforce the cap:**
1. **Authenticated users:** 5 route searches / 24h, server-enforced.
2. **Anonymous users:** per-IP + per-device throttle (coordinate with [[security-engineer]]) so the cap can't be reset by clearing state.
3. On cap hit → **block + upgrade-interest prompt** (capture the click as a demand signal).

**Cost control:**
4. Cache fresh-signal fetches at `(airport, hour)` if searches trigger them; **hard ceiling ~$0.002 per fetched search**, else serve base-rate only.

**Do NOT build in phase 1:** billing, paid tiers, API keys/quotas, seat management, B2B feed. Gating logic beyond the single 5/day cap is out of scope.

## Handoff → [[marketing]]

- Working name leaning **FlightPal**; positioning **"guarantee the best flight for your buck"** (per team pivot).
- Phase-1 message: **free flight-reliability route search, 5/day.** No price points to communicate yet.
- Still **do NOT market on out-predicting Google/FlightAware** ([[differentiation-thesis]]) — sell transparency + route-shopping.

---

## Appendix — DEFERRED to a later phase (kept for when interest is proven)

> Not in phase 1. Revisit once the free-limited MVP shows demand (cap-hit rate, upgrade-prompt clicks). **B2B is dropped per team decision — the ladder below is B2C-only.**

- **Paid consumer ladder** ([[tier-matrix]]): Plus (~$39/yr) and Pro (~$59/yr), anchored under/at Flighty's measured $59.99/yr ceiling — alerts, full route analytics, historical depth, unlimited (fair-use) searches. Live per-flight predictions become the metered paid unit ([[metering-unit]] LP definition).
- **Action affiliate** (rebook/insurance rev-share, EU-skewed) — near-$0 delivery cost, layerable once there's an audience.
- **Unit economics & margins** for the above: [[unit-economics]].
- **B2B feed / API (TMCs, insurers): DROPPED.** Thinking retained in [[tier-matrix]]/[[unit-economics]] history only; not a roadmap item.

## Deferred open questions

- [ ] After MVP: measure cap-hit rate + upgrade-prompt clicks to size paid-tier demand #task/sales 🔼 📅 2026-10-15
- [ ] Confirm route-search fresh-fetch cost via load test before any paid launch #task/sales ⛓ [[staff-ml-engineer]] 📅 2026-10-15

## Sources

- [OpenWeather One Call 3.0 pricing](https://openweathermap.org/api/one-call-3) — accessed 2026-08-08 *(measured)*
- [Flighty pricing $59.99/yr](https://flighty.com/pricing) — accessed 2026-08-08 *(measured, deferred-tier anchor)*
- Cross-refs: [[metering-unit]], [[tier-matrix]], [[unit-economics]], [[research-summary]], [[differentiation-thesis]], [[personas]]
