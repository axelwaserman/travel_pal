---
type: engineering
title: Flight Data Sources — APAC & Middle East
tags: [engineering, data, apac, middle-east, otp, backfill, regions]
status: draft
updated: 2026-08-10
---

# Flight Data Sources — APAC & Middle East

> Is there a free public BTS-equivalent for APAC/ME, or is it commercial-only? Scan for a region-partitioned spine (`model_apac`, `model_me`). Consumes [[data-acquisition-scan]], [[ingestion-backfill]]. Feeds [[regional-data-feasibility]]. Budget: **≤€50/mo total data**.

> [!important] Blunt answer
> **No true BTS-equivalent exists for APAC/ME.** Only **Australia (BITRE)** and **India (DGCA)** publish free, structured, downloadable OTP — and **both are aggregate (airline/route × month), not flight-level with actual times + cause codes** like BTS/ASQP. Everything else — **China, South Korea, Singapore, Japan (flight-level), the entire Gulf/ME** — is **commercial-only or not published**. For a *flight-level* APAC/ME model, you are effectively **paywalled**; the only budget-fit commercial source is **AeroDataBox (~$5/mo)**.

## 1. Government / open-data OTP (the free-BTS-equivalent question)

| Country | Source | Granularity | History | License / commercial | Cost | Verdict |
|---|---|---|---|---|---|---|
| **Australia** 🇦🇺 | **BITRE** Domestic OTP (`bitre.gov.au`, `data.gov.au`) | **Aggregate**: airline × route × month, on-time %, cancellations (not per-flight, no cause codes) | monthly, long time series (2003–) | data.gov.au **CC BY** — commercial OK ✅ (measured) | **free** | **Best free APAC source.** Domestic only. Base-rates, not flight-level. |
| **India** 🇮🇳 | **DGCA** via `data.gov.in` (OGD) + Dataful.in (CSV/XLSX/Parquet) | **Aggregate**: airline-wise monthly OTP, **only 4 metros** (DEL, BOM, BLR, HYD); ≤15-min arrival def | monthly, 2009– | OGD India Gov / ODbL — commercial OK ✅ (measured/*assumed* per-set) | **free** | **Second-best free.** Coarse (4 airports, airline-level). |
| **Japan** 🇯🇵 | **JCAB/MLIT** "information disclosure" OTP | **Aggregate** airline-level %, Japanese-language reports; no clean flight-level open set | annual/monthly | gov, terms unclear *(assumed)* | free | Weak — aggregate + language barrier. Base-rate only. |
| **South Korea** 🇰🇷 | MOLIT / `airportal.go.kr` | No dedicated open OTP dataset found (measured: search returned none) | — | — | — | **Effectively unavailable** as open data. |
| **China** 🇨🇳 | CAAC | No open flight-level; aggregate annual bulletins only | — | — | — | **Commercial-only** (VariFlight/Cirium dominate). |
| **Singapore** 🇸🇬 | CAAS / Changi | Live flight status on site; **no open OTP dataset** *(assumed)* | — | — | — | Commercial-only. |
| **Gulf / ME** 🇦🇪🇶🇦 | UAE GCAA; Emirates/Qatar/Etihad | Carriers/regulators **do not publish** OTP | — | — | — | **No free data. Commercial-only.** |

**Takeaway:** free gov OTP in APAC/ME = **Australia + India only**, and both are **base-rate aggregates** — good enough for booking-time route/carrier reliability and a *coarse* regional model, **not** for a flight-level day-of model (no actual times, no `LateAircraftDelay`-style labels — see [[data-acquisition-scan]] §0).

## 2. Commercial global providers — APAC/ME coverage vs budget

| Provider | APAC/ME coverage | Flight-level? actual times / cause? | History | License | Cost vs €50/mo |
|---|---|---|---|---|---|
| **AeroDataBox** | Global incl APAC/ME | Yes — status, actual times, delay stats | historical + live | commercial OK ✅ | **~$5/mo** ✅ **only budget-fit flight-level source** |
| **aviationstack** | Global, 250+ countries | Yes — status + historical | historical | commercial OK | **$49.99/mo** = entire budget ⚠️ |
| **AviationEdge** | Global | Yes — schedules/status/historical | historical | commercial | subscription, tens of $/mo *(assumed)* — likely tight |
| **FlightAware AeroAPI** | Global ADS-B (strong where ADS-B dense) | Yes — actual times, Foresight | live + recent | commercial OK ✅ | Personal ~$5/mo free, $0.002/q — fits at low volume ✅ |
| **ADS-B Exchange** | Global ADS-B | Raw positions (derive OTP yourself) | 10yr backfill **subscribers-only**, enterprise annual | commercial = enterprise ⚠️ | RapidAPI $10/mo/10k (commercial ambiguous) |
| **OAG** | Strong APAC OTP + schedules | Aggregate OTP + schedules | deep | enterprise | **enterprise** ❌ over budget |
| **Cirium** | Global incl APAC/ME/China ("gold standard", 600+ sources) | Flight-level OTP + predictive | deep | enterprise | **enterprise** ❌ over budget |
| **VariFlight** | **China/APAC specialist** | Flight-level OTP, delay analytics | deep | enterprise | **enterprise** ❌ (but the China answer if funded) |
| **OpenSky** | Global ADS-B, **thins over parts of Asia/ME** | Positions → derive | historical | **non-commercial** ❌ (confirmed) | free — **backtest/dev only** |

## 3. Region-by-region verdict (for the region-partitioned spine)

| Region | Free viable under budget? | Path |
|---|---|---|
| **Australia** | ✅ **Yes** (BITRE, free, base-rate) | Ship a coarse `model_apac_au` on BITRE base-rates now |
| **India** | ✅ **Yes** (DGCA, free, base-rate, 4 metros) | Base-rate route analytics for metros |
| **Japan / Korea** | ⚠️ aggregate-only / none | Base-rate at best; not worth MVP effort |
| **China** | ❌ commercial-only (VariFlight/Cirium) | Defer to funded phase |
| **Singapore / SE-Asia** | ❌ commercial-only | AeroDataBox if we must; else defer |
| **Middle East / Gulf** | ❌ **no free data at all** | Fully commercial; defer to funded phase |
| **Flight-level, any APAC/ME** | ⚠️ only **AeroDataBox (~$5/mo)** fits budget | Live/recent only; no cheap deep history |

## 4. Recommendation for MVP

1. **APAC foothold = Australia (BITRE) + India (DGCA)**, free, **base-rate granularity only** — booking-time route/carrier reliability, not flight-level day-of.
2. **Flight-level APAC/ME** within budget = **AeroDataBox ~$5/mo** (global) + **FlightAware AeroAPI Personal** (~free spot); OpenSky for **non-commercial backtest** only.
3. **Skip for MVP** (commercial/enterprise-paywalled): China, Gulf/ME, Singapore, Korea, Japan-flight-level, and all of Cirium/OAG/VariFlight until a funded phase.
4. **Consistency with region-partition design:** free APAC data is lower-fidelity than US-BTS, so `model_apac` will be **weaker/coarser** than `model_us`. Set expectations: APAC/ME are **base-rate transparency plays**, not calibrated day-of forecasts, until a paid feed is budgeted. Feed granularity gap → [[regional-data-feasibility]].

## Open questions
- [ ] Confirm BITRE/DGCA redistribution terms for the public edge tier (both look CC BY / OGD-open). `#task/eng 🔼`
- [ ] Is base-rate-only granularity enough for an APAC product surface, or does it need AeroDataBox flight-level? ⛓ [[staff-ml-engineer]] + [[sales]]. `#task/eng`
- [ ] Gulf/ME has zero free data — is ME worth any MVP effort, or defer entirely? `#task/product ⛓ [[marketing]]`

## Sources
- [BITRE Domestic OTP](https://www.bitre.gov.au/statistics/aviation/otphome) · [data.gov.au OTP dataset](https://data.gov.au/data/dataset/domestic-airline-on-time-performance) — accessed 2026-08-10
- [DGCA OTP on data.gov.in](https://www.data.gov.in/resource/airline-wise-details-monthly-time-performance-data-respect-scheduled-domestic-airlines) · [Dataful DGCA collection](https://dataful.in/collections/420/) · [india-aviation-traffic (ODbL)](https://github.com/Vonter/india-aviation-traffic) — accessed 2026-08-10
- [JCAB/MLIT OTP context (Skymark)](https://smart.skymark.co.jp/en/news/detail/1193617_1793.html) · [SIA/APAC punctuality — MalayMail](https://www.malaymail.com/news/singapore/2025/01/03/sia-climbs-to-asia-pacifics-top-three-for-airline-punctuality-in-2024-after-jal-and-ana/161879) — accessed 2026-08-10
- [Cirium OTP FAQ](https://www.cirium.com/resources/on-time-performance/on-time-performance-faq/) · [VariFlight OTP analytics](https://dataworks.variflight.com/products/data-analysis/) · [OAG OTP data](https://www.oag.com/on-time-performance-data) — accessed 2026-08-10
- [AeroDataBox pricing](https://aerodatabox.com/pricing) · [aviationstack pricing](https://aviationstack.com/pricing) · [FlightAware AeroAPI pricing](https://www.flightaware.com/commercial/aeroapi/v3/pricing.rvt) · [ADS-B Exchange RapidAPI](https://rapidapi.com/adsbx/api/adsbexchange-com1/pricing) · [OpenSky FAQ (non-commercial)](https://opensky-network.org/about/faq) — accessed 2026-08-10
