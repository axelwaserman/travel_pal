---
type: research
title: B2C Use-Case Gap Analysis — Where a Calibrated/Transparent Tool Wins
tags: [product, research, competitors, b2c, use-cases]
status: draft
updated: 2026-08-10
---

# B2C Use-Case Gap Analysis

> B2C only (B2B docked). For three concrete consumer jobs: is it already solved, and where is the gap for our **transparency + calibration + reliability-route-shopping** wedge? Extends [[competitors]], [[personas]], [[differentiation-thesis]].

## TL;DR ranking (gap size × our fit)

| Rank | Use case | Verdict | Gap size | Our fit | MVP call |
|------|----------|---------|----------|---------|----------|
| **1** | **A — Pre-booking reliability shopping** | **GAP** | Large | **High** | ⭐ **Anchor the MVP** |
| 2 | C — Day-of delay foresight | Partial (Flighty owns it) | Medium | Medium | Phase-2 companion |
| 3 | B — Disruption rebooking | Solved by incumbents w/ booking rails | Small-for-us | Low | **Trap — skip** |

Note: **App in the Air is defunct** (shut down 2024-10-19) — excluded as a live competitor. Freebird is defunct as a standalone (acquired by Capital One 2020; tech now = Capital One "Flight Disruption Assistance").

---

## USE CASE A — Pre-booking decision support (reliability route-shopping)

*"Help me book the best option given price vs reliability vs timing."*

| Product | Does it solve A? | Evidence |
|---------|------------------|----------|
| **Google Flights** | **Partial** — flags individual flights "often delayed" at booking, ≥80% confidence, from historical OTP | measured (multiple sources) |
| **Kayak** | No reliability sort/filter found — sorts price/duration/stops/times | not offered (verified absent in coverage) |
| **Flighty / TripIt / FlightAware** | No — these are trackers/itinerary tools, **not booking search** | measured |
| **Hopper** | No — predicts *price*, not reliability, for shopping | measured |
| **Airline apps** | No — single-carrier, can't cross-shop | measured |

**What's missing:** nobody offers **sortable, quantified, multi-criteria reliability shopping.** Google's "often delayed" is a **black-box binary flag on one flight**, not a *ranked, calibrated reliability score you can trade off against price and timing across carriers.* You cannot sort a results list by on-time probability, see the distribution (not just a warning), or understand *why* a route is reliable.

**Our fit: HIGH.** This is precisely the lakehouse route-analytics + transparency + calibration wedge from [[differentiation-thesis]]. It is **batch historical analytics** — no live booking rails, no deep fresh-data feed required — so it is also the **cheapest to serve** (edge DuckDB-WASM) and the most compatible with the ≤€50/mo data budget in [[regional-data-feasibility]] (ADRR-trained historical spine is enough). Defensible because Google won't expose a transparent methodology and incumbents lack the cross-carrier reliability-shopping UX.

---

## USE CASE B — Disruption rebooking ("my flight was cancelled, save me time")

*The human suspected this is niche + complex. Confirmed: it's a **trap** for us.*

| Product | Does it solve B? | Evidence |
|---------|------------------|----------|
| **Airline apps** (Delta "Rebook Me", United auto-rebook) | Yes — auto-present rebooking + vouchers on cancel; but "rarely the best available" | measured/reported |
| **TripIt Pro** | Yes — "Alternate Flights" gives **unbiased cross-airline** rebooking options | measured (TripIt help docs) |
| **Capital One Flight Disruption Assistance** (ex-Freebird) | Yes — pre-purchased coverage auto-rebooks | measured |
| **Hopper** | Yes — Premium Disruption Assistance rebook/refund | measured |

**Why it's a trap for us:** rebooking is an **execution + inventory + ticketing** problem, not a prediction/transparency problem. The players who solve it own **booking rails** (airlines, OTAs, card issuers) or **PNR access** (TripIt). We have neither. Our wedge (calibration, transparency, reliability history) adds ~nothing once the flight is *already cancelled* — the job is "find and book a seat fast," which needs live inventory and payment integration we don't have. It is also crowded and increasingly commoditized (every major US airline now exposes self-service rebooking). **Skip.**

---

## USE CASE C — Day-of status foresight ("will it be delayed — when do I leave?")

| Product | Does it solve C? | Evidence |
|---------|------------------|----------|
| **Flighty** | **Yes, well** — ML delay prediction up to 6h ahead, with *reason* (late aircraft/ATC/ground-stop), alerts before the airline | measured (vendor + reviews) |
| **Google Flights** | Partial — live delay status/prediction, confidence-gated | measured |
| **TripIt Pro** | Partial — real-time delay/gate/cancel alerts, from 3 days out | measured |
| **Airline apps** | Partial — notify of their own delays (conflicted incentive to under-warn) | measured/[[competitors]] |
| **"Leave-by" recommendation** | **Not integrated anywhere verified** — standalone calculators (OnTimer, TakeoffTimer) exist separately; **could not confirm Flighty or any tracker fuses delay-forecast + traffic/TSA into a leave-by time** | assumed/unverified |

**What's missing:** the core "will it be delayed" foresight is **already solved and monetized by Flighty** ($59.99/yr) — attacking it head-on means fighting a funded incumbent on its home turf. The genuine unmet micro-gap is the **integrated "leave-by" synthesis** (delay forecast + when-to-leave) and **cross-platform reach** (Flighty is iOS-only). Plus transparency/calibration as a trust differentiator.

**Our fit: MEDIUM.** Real demand, but thin differentiation and a **costlier data profile** — day-of foresight needs *fresh live feeds*, which strain the ≤€50/mo budget (see [[regional-data-feasibility]]; AeroDataBox live tier). Best as a **Phase-2 companion** to A, not the anchor.

---

## Recommendation — anchor the MVP on **Use Case A**

Use Case A has the **largest unmet gap** (no one does transparent, sortable, multi-criteria reliability shopping — Google only flashes a binary warning) **and** the **best fit** (it *is* our lakehouse + transparency + calibration wedge), **and** the **lowest cost to serve** (batch historical analytics on an ADRR-trained spine, edge DuckDB-WASM, no booking rails or expensive live feeds). B is a trap (needs booking rails we lack); C is a Flighty rematch (defer to Phase 2, adding the leave-by synthesis + cross-platform).

## Handoffs

- → [[staff-product-engineer]]: MVP = **reliability route-shopping** UI over pre-aggregated historical OTP; requires a *ranking/scoring* layer (calibrated on-time probability + confidence), sortable/filterable against price & timing. Batch-first; no live-booking integration in v1.
- → [[personas]]: A serves the **Optimizing Nomad (P1)** best and the **Anxious Occasional Flyer (P2)** via a simple "reliability score." C would later serve P2 day-of.
- → [[sales]]: A is a free/low-cost acquisition surface; monetization likely via alerts/premium analytics (C) layered on top later.

## Sources

- [Google Flights displays live delay info — Upgraded Points](https://upgradedpoints.com/news/google-flights-live-delay-information/) · [How to predict delays with Google Flights — Forbes](https://www.forbes.com/sites/bishopjordan/2018/03/20/how-to-predict-flight-delays-using-google-flights/) — accessed 2026-08-10
- [Google Flights vs KAYAK — Going](https://www.going.com/guides/google-flights-vs-kayak-how-to-use-both-to-find-cheap-flights) — accessed 2026-08-10 (Kayak filters: price/duration/stops/times; no reliability sort found)
- [TripIt Pro Alternate Flights (help)](https://help.tripit.com/en/support/solutions/articles/103000063402-tripit-pro-alternate-flights) · [TripIt Flight alerts](https://help.tripit.com/en/support/solutions/articles/103000063296-flight-alerts) · [Fare Tracker](https://help.tripit.com/en/support/solutions/articles/103000063380-fare-tracker) — accessed 2026-08-10
- [App in the Air shuts down 2024-10-19 — World Traveller 73](https://worldtraveller73.com/2024/09/26/app-in-the-air-shuts-down-what-users-need-to-know/) · [AlternativeTo](https://alternativeto.net/news/2024/9/app-in-the-air-to-shut-down-on-september-19-2024-users-advised-to-export-their-data-now) — accessed 2026-08-10
- [Capital One acquires Freebird — Skift (2020)](https://skift.com/2020/08/26/capital-one-acquires-freebirds-flight-disruption-tech/) · [Capital One Flight Disruption Assistance — TPG](https://thepointsguy.com/news/capital-one-rapid-rebook/) — accessed 2026-08-10
- [United auto-rebook app feature (2023)](https://united.mediaroom.com/2023-06-22-Uniteds-New-App-Feature-Helps-Customers-Re-book-and-Receive-Meal-and-Hotel-Vouchers-Automatically) · [Delta Rebook Me](https://www.delta.com/us/en/change-cancel/delayed-or-canceled-flight) · ["your airline rebooked… but you may have better options" — Yahoo](https://creators.yahoo.com/lifestyle/story/your-airline-rebooked-your-canceled-flight--but-you-may-have-better-options-125148104.html) — accessed 2026-08-10
- [Flighty delay prediction / airport disruption alerts — TechBuzz](https://www.techbuzz.ai/articles/flighty-adds-real-time-airport-disruption-alerts) · [Flighty warned me before the airline — WhistleOut](https://www.whistleout.com/CellPhones/Guides/flighty-for-flight-tracking-and-alerts) — accessed 2026-08-10
- Leave-by calculators (standalone, not integrated): [OnTimer](https://www.ontimer.app/airport-time-to-leave-calculator) · [TakeoffTimer](https://www.takeofftimer.com/when-to-leave-calculator) — accessed 2026-08-10
