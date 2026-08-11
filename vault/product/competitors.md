---
type: research
title: Competitor Teardown — Flight Delay Prediction
tags: [product, research, competitors]
status: draft
updated: 2026-08-08
---

# Competitor Teardown — Flight Delay Prediction

> Landscape for a product that **predicts P(delayed) + delay-minutes**. See [[demand-evidence]], [[personas]], [[differentiation-thesis]], [[research-summary]].

The market splits into four bands. **Prediction as a free feature is already commoditized** by Google and Apple; the defensible money is in *action* (rebooking, compensation, insurance payouts) and *B2B feeds* (airlines/airports/insurers).

## Teardown table

| #   | Product                                      | Band                       | Predicts?                                                                 | Data sources (claimed)                              | Business model                                                | Public price                     | Gap we could exploit                                                                          |
| --- | -------------------------------------------- | -------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------- | -------------------------------- | --------------------------------------------------------------------------------------------- |
| 1   | **Google Flights**                           | Consumer, free             | Yes — P(delay), reason, weeks ahead; only flags at ≥80% confidence        | Historical records + ML; live ATC/weather (claimed) | Free (ecosystem/ads)                                          | $0                               | No route-level *shop-time* analytics; no action layer; US-centric surfacing                   |
| 2   | **Apple/Flighty-style ML in OS** (Flighty)   | Consumer premium (iOS)     | Yes — late-aircraft, ATC, ground-stop, up to 6h ahead                     | ADS-B, ATC feeds, ML                                | Freemium subscription                                         | Pro **$59.99/yr**, lifetime $299 | iOS-only; personal-tracker framing, not "should I book route X"; no lakehouse route analytics |
| 3   | **FlightAware** (Misery Map / **Foresight**) | Consumer free + **B2B ML** | Yes — Foresight = ETAs, runway, taxi-out for airlines/airports            | Global ADS-B network + ML                           | Free map; B2B licensing / AeroAPI                             | B2B (opaque), AeroAPI metered    | Consumer-facing predictive *shopping* UX is thin; B2B priced for enterprises                  |
| 4   | **Hopper**                                   | Consumer fintech           | Price prediction (25B+ price points); disruption = rebooking not forecast | Fare + operational data                             | Fintech: fees on Premium Disruption Assistance / rebooking    | Add-on fee per trip              | Sells the *cure* (rebook/refund), not a transparent delay forecast                            |
| 5   | **AirHelp**                                  | Post-hoc compensation      | No (reactive)                                                             | EU261/DOT eligibility engine                        | 35% of recovered comp (50% if court); **AirHelp+** €36–€90/yr | Sub or contingency               | Only pays *after* disruption; EU-centric; nothing predictive                                  |
| 6   | **Compensair**                               | Post-hoc compensation      | No                                                                        | Same regime                                         | 25% of recovered comp                                         | Contingency                      | Same as AirHelp; cheaper cut                                                                  |
| 7   | **Blink Parametric**                         | B2B insurtech infra        | Trigger-based (delay ≥Xh → payout/lounge)                                 | Real-time flight status feeds                       | White-label to insurers (Cover-More, TIS)                     | B2B                              | Powers *insurers*; needs an underwriter; not a consumer forecast                              |
| 8   | **Sensible Weather**                         | B2B/B2C parametric         | Weather-trigger, not flight-delay ML                                      | Weather data                                        | Guarantee add-on at checkout                                  | % of booking                     | Weather only, not flight-operations delay                                                     |
| 9   | **DelayGuard.ai**                            | Consumer free              | Yes — US domestic, 65+ airports                                           | Weather + historical, "no account"                  | Free (unclear monetization)                                   | $0                               | Thin data spine, US-only, no route/carrier depth; monetization unproven                       |
| 10  | **FlightRadar24 / FlightStats**              | Tracker / data             | Tracking + status; FlightStats sells ratings                              | ADS-B, ops feeds                                    | Subscription + data licensing                                 | ~$35–90/yr / B2B                 | Tracking, not decision-grade P(delay) shopping                                                |
| 11  | **Cirium** (ex-FlightStats/OAG-adjacent)     | B2B data/analytics         | On-time performance analytics, Ezy predictions                            | Proprietary global feeds                            | Enterprise data licensing                                     | Enterprise                       | Not consumer; expensive; our edge is cheap edge-analytics                                     |
| 12  | **Airline apps** (United/Delta/AA)           | Incumbent                  | Increasingly predict own delays; auto-rebook                              | First-party ops data                                | Bundled                                                       | Free                             | Single-carrier, conflicted incentive to under-warn; no cross-carrier compare                  |

## Per-competitor notes (signal beyond the table)

- **Google Flights** — the existential threat. Free, in the search path, and reportedly weeks-ahead with a confidence gate. *Caveat:* widely-repeated "89.3% / MIT Lincoln Lab / 28 carrier APIs / 7.2B records" figures trace to AI-content-farm SEO pages, **not** a primary Google or MIT source — treat as **unverified/likely fabricated**, do not cite downstream.
- **Flighty** — vendor claims ">95% accurate" delay prediction (marketing, **assumed**). Proves consumers *will pay* ~$60/yr for early, explained delay signals. Weakness: iOS-only, personal-tracker JTBD, not route-shopping.
- **FlightAware Foresight** — the real ML benchmark; but it is sold to operators, and its consumer surface (Misery Map) is descriptive, not a personalized forecast. B2B is where prediction has proven willingness-to-pay.
- **Hopper / AirHelp / Blink** — collectively show the money is in the *action*: rebook, claim, or insure. A pure forecast without an action hook monetizes poorly.

## Sources

- [Best travel apps for flight delays (2026) — Travo](https://travo.me/blog/best-travel-app-for-flight-delays) — accessed 2026-08-08
- [Flighty delay predictions (help)](https://flighty.com/help/delay-predictions) · [Flighty pricing](https://flighty.com/pricing) — accessed 2026-08-08
- [Flighty adds ML delay prediction — TechCrunch, 2024-08-06](https://techcrunch.com/2024/08/06/flightys-popular-flight-tracking-app-can-now-predict-delays-using-machine-learning/) — accessed 2026-08-08
- [Google Flights will now predict delays — TechCrunch, 2018-01-31](https://techcrunch.com/2018/01/31/google-flights-will-now-predict-airline-delays-before-the-airlines-do/) — accessed 2026-08-08
- [FlightAware Foresight Labs](https://go.flightaware.com/foresightlabs) · [FlightAware MiseryMap](https://www.flightaware.com/miserymap/) — accessed 2026-08-08
- [Hopper Premium Disruption Assistance](https://www.hopper.com/product/premium-disruption-assistance) — accessed 2026-08-08
- [AirHelp vs Compensair 2026 — Megaport blog](https://megaport.hu/blog/flight-delay-compensation-in-2026-airhelp-vs-compensair-which-one-is-better/) · [AirHelp+ pricing — Travel-Dealz](https://travel-dealz.com/deal/airhelp-plus/) — accessed 2026-08-08
- [Blink Parametric flight disruption](https://blinkparametric.com/blink-parametric-platform/blink-flight-disruption/) · [Parametric travel insurance — Matador](https://matadornetwork.com/read/parametric-insurance-for-travel/) — accessed 2026-08-08
- [DelayGuard.ai](https://www.delayguard.ai/flight-delay-prediction) — accessed 2026-08-08
