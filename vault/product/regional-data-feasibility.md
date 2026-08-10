---
type: research
title: Regional Data Feasibility & Monetization — EU vs US
tags: [product, research, data-sourcing, monetization, eu]
status: draft
updated: 2026-08-09
---

# Regional Data Feasibility & Monetization — EU vs US

> Spike: is a commercial-safe EU historical delay spine reachable under **€50/mo**, and which region should v1 target? Extends [[research-summary]], [[differentiation-thesis]], [[competitors]].

## Bottom line

A **legally-clean, deep, flight-level EU historical spine that is also commercial and ≤€50/mo does not exist.** The gold-standard EU on-time-performance data (OAG, Cirium) is enterprise-priced (well over budget); the free/rich EU sources (Eurocontrol) are **non-commercial or R&D-only**. The affordable commercial APIs (AeroDataBox, aviationstack) are commercial-clean but ship **shallow history (~±365 days) and lower data quality**. **Practical path: Eurocontrol ADRR (free) to train/validate the model under its R&D terms + a cheap commercial API (AeroDataBox ~€5–30/mo) as the rolling live serving spine that grows forward.** Deep backfill must be bought later or grown over time.

## Q1 — EU commercial-safe punctuality/delay data

Legend: License = commercial product use allowed? · Cost vs €50/mo cap.

| Source | Coverage | Granularity | Latency | Commercial license | Cost | Verdict |
|--------|----------|-------------|---------|--------------------|------|---------|
| **Eurocontrol CODA / PRU** (ansperformance.eu) | Pan-EU network + major airports | **Aggregated** (monthly punctuality/delay-cause), not flight-level | ~monthly | **No** — "reproduced… to the extent justified by non-commercial use (not for sale)" | Free | ❌ license blocks product use; too coarse anyway |
| **Eurocontrol ADRR** (R&D Data Archive, OneSky) | Pan-EU, ~12M flights | **Flight-level**, rich (routes, delays, ops) | **2-yr delay, only 4 months/yr** (Mar/Jun/Sep/Dec) | **R&D only** — commercial = "selling the data or products containing it"; R&D projects with potentially-commercial outcomes OK *if not reliant on continued use* | Free | ⚠️ **Great for model TRAINING/R&D, not a live commercial serving spine** |
| **UK CAA punctuality stats** | UK airports only | Route/airline monthly | Monthly | Murky — OGL allows commercial, **but CAA adds "no data may be sold on to a third party"** | Free | ⚠️ UK-only; usable for derived analytics with care, resale restricted |
| **OAG** | Global incl. EU | Flight-level schedules + status/OTP | Real-time + historical | **Yes** | Enterprise custom (**≫ €50/mo**) | ❌ over budget |
| **Cirium** (ex-FlightStats) | Global, 600+ sources, 15+ yr OTP | Flight-level OTP, deepest history | Real-time + historical | **Yes** | Enterprise custom (**≫ €50/mo**) | ❌ over budget (gold standard, unaffordable) |
| **FlightAware AeroAPI** | Global | Flight-level status/history (from 2011) | Real-time + historical | **Yes** | Usage-based; first $1,000/mo at list price; "result set" = 15 records | ❌/⚠️ meaningful EU backfill **exceeds €50/mo**; fine for tiny live volume |
| **aviationstack** | Global | Historical/schedules (paid tiers) | Real-time + historical | **Yes** | **Basic $49.99/mo** = 10k req (historical locked to paid) | ⚠️ **≈ at the cap**; quality/depth concerns; thin history |
| **AviationEdge** | Global | Real-time + historical + reference | Real-time + historical | **Yes** | **No free tier; price not public** | ⚠️ flag — unknown cost, request quote |
| **AeroDataBox** (RapidAPI/API.market) | Global incl. EU | Flight-level status + **delay**, schedules | Real-time; **history ±365 days**, 7-day page/call | **Yes** (via RapidAPI sub) | **Free tier (600 units/mo); paid from ~$5/mo** | ✅ **best budget fit** for live EU flight-level delay data, but shallow history |
| **ADS-B Exchange** | Global (crowd ADS-B, "unfiltered") | Raw positions (derive delay yourself) | Real-time | **Yes** (enterprise/RapidAPI feeds) | RapidAPI tiers exist; enterprise for bulk — **assumed** | ⚠️ raw, not OTP; derivation cost; confirm tier price |
| **OpenSky** | EU/US strong, thins elsewhere | Raw ADS-B state vectors | Real-time + historical | **No — non-commercial only** (confirmed) | Free (credits) | ❌ license blocks commercial |

**Reading:** the two free, high-quality EU sources are legally off-limits for a commercial product spine (CODA non-commercial; ADRR R&D-only + 2-yr/4-month latency). Everything commercial-and-affordable (AeroDataBox, aviationstack) trades away history depth and quality. The deep, clean, commercial spine (OAG/Cirium) is enterprise-priced.

## Q2 — Regional monetization (grounds/corrects the "EU stronger" lean)

**Refined conclusion: split by layer.** The *compensation/insurance action* layer monetizes overwhelmingly in **EU/UK**; the *consumer subscription prediction* layer is **US/global**.

- **EU/UK = the money for the action hook.** EU261/UK261 mandate **fixed cash up to €600 / £520** regardless of the traveler having to prove loss. An entire paying industry is built on it: AirHelp, Compensair, Flightright, AirAdvisor, EUclaim — all EU261-native. "The biggest and most predictable payouts remain EU261-style claims for flights departing/arriving Europe." (**measured** regime; vendor-confirmed.)
- **US = weak action hook.** No fixed compensation; US is **refunds-only** (3h dom / 6h intl) and the DOT cash-compensation rule was **withdrawn 2025-11-17** (see [[research-summary]]). US comp is "mostly limited to denied boarding." (**measured**.)
- **US/global = where the pure prediction subscription lives.** Flighty ($59.99/yr) and Google Flights are US-anchored/global; they monetize (or give away) the forecast regardless of region. Consumer-prediction WTP is not EU-specific.

**Net:** the earlier "EU is the stronger market" lean holds **specifically for the monetizable action/insurance layer** — which is exactly the defensible layer [[differentiation-thesis]] pointed to. It does **not** hold for the commoditized consumer forecast (that's a US/global, low-WTP game).

## The core tension (for v1 targeting)

The region with the **best monetization hook (EU)** has the **worst cheap-commercial data availability**. The region with **free, easy data (US = BTS)** has the **weakest monetization hook** and the most commoditized incumbents (Google). There is no region where both are easy under €50/mo.

## Recommendation

**v1 → EU/UK, on the monetizable action/insurance hook, with a hybrid data spine:**
1. **Model R&D/training:** Eurocontrol **ADRR** (free, flight-level, rich) — permitted under its R&D terms.
2. **Live serving spine:** **AeroDataBox** (~€5–30/mo, commercial-clean, global incl. EU) — accept a **rolling ~12-month window that grows forward**, not a deep backfill.
3. **Upgrade path:** when revenue justifies it, buy Cirium/OAG for deep history + SLA.

Accept that **deep historical EU backfill is not affordable at ≤€50/mo** — design for a forward-growing spine. If the human prefers zero data-license risk and lowest cost for a throwaway MVP, a **US/BTS** build is trivially free — but it lands in the weaker-monetization, Google-commoditized market and should be treated as a tech demo, not the commercial bet.

## Handoffs

- → [[staff-product-engineer]]: ingestion must support a **hybrid spine** (ADRR batch for training + AeroDataBox rolling live feed); design for a forward-growing window, not deep backfill. Budget cap ≤€50/mo is a hard constraint on feed choice.
- → [[sales]]: EU261/UK261 is the monetization engine — model the **action/insurance/B2B** tiers around EU/UK; treat US as consumer-subscription/global only.

## Sources

- [Eurocontrol — Our data](https://www.eurocontrol.int/our-data) · [CODA/ansperformance Aviation Intelligence Portal](https://ansperformance.eu/) — accessed 2026-08-09
- [Eurocontrol ADRR — Terms of Use (PDF)](https://www.eurocontrol.int/sites/default/files/2025-04/eurocontol-aviation-data-repository-research-terms-of-use.pdf) · [ADRR launch — 12M flights, free](https://www.eurocontrol.int/news/new-eurocontrol-rnd-data-archive-launched) — accessed 2026-08-09
- [UK CAA — Flight punctuality statistics 2026](https://www.caa.co.uk/data-and-analysis/uk-aviation-market/flight-punctuality/uk-flight-punctuality-statistics/2026/) · [Open Government Licence](https://en.wikipedia.org/wiki/Open_Government_Licence) — accessed 2026-08-09
- [Cirium — On-Time Performance FAQ](https://www.cirium.com/resources/on-time-performance/on-time-performance-faq/) · [OAG vs Cirium vs FlightAPI](https://www.flightapi.io/blog/cirium-vs-oag-vs-flightapi/) — accessed 2026-08-09
- [FlightAware AeroAPI v4 (pricing model)](https://www.flightaware.com/commercial/aeroapi/v4/) — accessed 2026-08-09
- [aviationstack pricing — SpotSaaS](https://www.spotsaas.com/product/aviationstack-api/pricing) · [Best flight APIs 2026 — Thunderbit](https://thunderbit.com/blog/best-flight-api-with-free-tiers) — accessed 2026-08-09
- [AeroDataBox — RapidAPI pricing](https://rapidapi.com/aedbx-aedbx/api/aerodatabox/pricing) · [AeroDataBox on API.market ($5/mo)](https://api.market/store/aedbx/aerodatabox) — accessed 2026-08-09
- [AirHelp vs Flightright (EU261 vs US)](https://www.airhelp.com/en/blog/airhelp-vs-flightright-which-flight-compensation-company-is-best-for-us-travelers/) — accessed 2026-08-09
- OpenSky non-commercial terms — confirmed in [[competitors]] / [[research-summary]] ([OpenSky FAQ](https://opensky-network.org/about/faq)) — accessed 2026-08-09
- ADS-B Exchange commercial tiers — **assumed / unconfirmed**, needs a direct quote check
