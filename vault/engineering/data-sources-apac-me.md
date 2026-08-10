---
type: engineering
title: Flight Data Sources — APAC & Middle East
tags: [engineering, data, apac, middle-east, otp, backfill, regions]
status: draft
updated: 2026-08-10
---

# Flight Data Sources — APAC & Middle East

> Exhaustive per-country scan for a region-partitioned spine (`model_apac`, `model_me`). **Two product zones matter** (per PR #13): the **FREE product** can lean on non-commercial sources (OpenSky, some gov data); the **PAID product** must use commercial-clean feeds only. Consumes [[data-acquisition-scan]], [[historical-nonus-sources]]. Feeds [[regional-data-feasibility]], [[ingestion-backfill]]. Budget: **≤€50/mo total**.

> [!important] Blunt answer
> **No true BTS-equivalent (free, flight-level, delay-labelled, cause codes) exists anywhere in APAC/ME.** The best free gov data is **aggregate OTP** (airline/route × month %). Free & structured: **Australia (BITRE)**, **India (DGCA)**, **Malaysia (MAVCOM)**. Aggregate-but-messy: **Japan, Vietnam**. Effectively nothing: **China, Korea, Singapore, Thailand, Indonesia, Philippines, entire Gulf/ME**. Flight-level anywhere in APAC/ME = **commercial** (AeroDataBox ~$5/mo the only budget-fit; Cirium/OAG/VariFlight enterprise).

## The two distinctions that decide fit

- **Granularity:** *flight-level* (per-flight actual times + cause codes, like BTS) vs *aggregate* (monthly airline/route on-time %). Aggregate → base rates only, no supervised delay label, no day-of features.
- **License zone:** *FREE product* tolerates non-commercial sources (OpenSky) — **caveat:** a free app from a for-profit may still count as "commercial use" under OpenSky terms; verify (*assumed* permissive here). *PAID product* needs commercial-clean.

## Per-country matrix

| Country | Gov open OTP? (granularity) | License / commercial | FREE-product path | PAID-product path |
|---|---|---|---|---|
| 🇦🇺 **Australia** | ✅ **BITRE** — airline × route × month OTP + cancellations (aggregate) | data.gov.au **CC BY**, commercial-OK (measured) | BITRE direct | **BITRE** (already commercial-clean) + AeroDataBox for flight-level |
| 🇮🇳 **India** | ✅ **DGCA** via data.gov.in / Dataful (CSV/Parquet) — airline monthly, **4 metros only** (DEL/BOM/BLR/HYD), aggregate | OGD India / ODbL, commercial-OK (measured/*assumed* per-set) | DGCA direct | DGCA + AeroDataBox flight-level |
| 🇲🇾 **Malaysia** | ✅ **MAVCOM** Airline & Airport Performance Dashboard — OTP + cancellations + delay types, dom + intl (aggregate); 85% STD target | gov dashboard; reuse terms **unclear** (*assumed*, verify) | MAVCOM dashboard | verify MAVCOM licence, else AeroDataBox/Cirium |
| 🇻🇳 **Vietnam** | ⚠️ **CAAV** publishes punctuality % via reports/press (airline-level, aggregate, no clean dataset) | gov press; not a dataset (*assumed*) | scrape CAAV releases (coarse) | AeroDataBox / Cirium |
| 🇯🇵 **Japan** | ⚠️ **JCAB/MLIT** "information disclosure" — airline-level %, Japanese-language reports | gov, terms unclear (*assumed*) | MLIT (coarse, JP) | Cirium / OAG |
| 🇹🇭 **Thailand** | ❌ **CAAT** publishes air-transport stats but **no OTP open data** found (measured: none) | — | none viable | AeroDataBox / Cirium |
| 🇰🇷 **South Korea** | ❌ MOLIT / `airportal.go.kr` — no dedicated open OTP dataset found (measured: none) | — | none viable | Cirium / OAG |
| 🇨🇳 **China** | ❌ **CAAC** — aggregate annual bulletins only; no open flight-level | — | OpenSky backtest only (non-commercial, thins over China) | **VariFlight** (China specialist) / Cirium — enterprise |
| 🇸🇬 **Singapore** | ❌ CAAS / Changi — live status only, no open OTP (*assumed*) | — | none viable | AeroDataBox / Cirium |
| 🇮🇩 **Indonesia** | ❌ no gov open OTP; via Cirium/OAG | — | none viable | AeroDataBox / Cirium / OAG |
| 🇵🇭 **Philippines** | ❌ CAAP — no open OTP (*assumed*) | — | none viable | AeroDataBox / Cirium |
| 🇦🇪🇶🇦🇸🇦 **Gulf / ME** (UAE GCAA, Qatar, Saudi GACA; Emirates/Qatar/Etihad) | ❌ **regulators + carriers do not publish** OTP (measured: none found) | — | OpenSky backtest only (non-commercial) | Cirium / OAG / AeroDataBox — **fully paywalled** |

## How the datasource path evolves: FREE vs PAID

- **FREE product** (route-shopping base rates, no metering revenue): use **gov aggregates** (AU/IN/MY, plus JP/VN where scrapeable) + **OpenSky** (non-commercial, EU/US-strong, APAC-thin) for a coarse global base-rate map. Legal caveat on OpenSky-in-a-free-commercial-app stands — verify.
- **PAID product** (metered predictions): every region must switch to a **commercial-clean** feed. Cheapest global = **AeroDataBox (~$5/mo)** — but shallow history ([[historical-nonus-sources]]); deep/labelled = **Cirium/OAG/VariFlight (enterprise, ≫€50/mo)**.
- **The gap:** AU/IN/MY give commercial-clean *aggregates* for free — good enough for a paid *base-rate* surface, but not for a flight-level day-of model. Flight-level paid APAC/ME within budget = AeroDataBox only, and it's forward/shallow, so **start accruing daily now** ([[historical-nonus-sources]] §Start-now plan).

## Region verdict (for the region-partitioned spine)

| Region | Free viable? | Path |
|---|---|---|
| Australia | ✅ (commercial-clean aggregate) | `model_apac_au` base rates now |
| India | ✅ (aggregate, 4 metros) | metro base rates |
| Malaysia | ✅ (aggregate; verify licence) | base rates |
| Japan / Vietnam | ⚠️ aggregate/messy | coarse base rates only |
| China / Korea / Singapore / Thailand / Indonesia / Philippines | ❌ commercial-only | AeroDataBox (shallow) or defer |
| Middle East / Gulf | ❌ **no free data at all** | commercial or defer entirely |
| Flight-level, any APAC/ME | ⚠️ only **AeroDataBox ~$5/mo** in budget | forward-accrue daily |

## Recommendation for MVP

1. **Free APAC foothold = Australia + India + Malaysia** (commercial-clean-ish aggregates) → booking-time route reliability, not day-of.
2. **Flight-level APAC/ME** within budget = **AeroDataBox ~$5/mo**; **start daily capture now** to build the deep history no one sells cheap.
3. **Defer** China (VariFlight/Cirium enterprise) and **Gulf/ME** (zero free data) to a funded phase.
4. `model_apac`/`model_me` on free data are **base-rate transparency plays**, weaker than `model_us`, until a paid feed is budgeted → granularity gap tracked in [[regional-data-feasibility]].

## Open questions
- [ ] Verify BITRE/DGCA/MAVCOM redistribution terms for the free tier. `#task/eng 🔼`
- [ ] Is base-rate granularity enough for an APAC surface, or is AeroDataBox flight-level required? ⛓ [[staff-ml-engineer]]. `#task/eng`
- [ ] Gulf/ME has zero free data — worth any MVP effort, or defer entirely? `#task/product ⛓ [[marketing]]`

## Sources
- [BITRE Domestic OTP](https://www.bitre.gov.au/statistics/aviation/otphome) · [data.gov.au OTP dataset](https://data.gov.au/data/dataset/domestic-airline-on-time-performance) — accessed 2026-08-10
- [DGCA OTP on data.gov.in](https://www.data.gov.in/resource/airline-wise-details-monthly-time-performance-data-respect-scheduled-domestic-airlines) · [Dataful DGCA collection](https://dataful.in/collections/420/) — accessed 2026-08-10
- [MAVCOM performance dashboard (CAAM release)](https://www.caam.gov.my/newsroom/mavcom-announces-enhanced-airline-and-airport-performance-dashboard/) · [MAVCOM](https://www.mavcom.my/) — accessed 2026-08-10
- [CAAV punctuality (VietnamNews)](https://vietnamnews.vn/economy/417611/punctuality-rate-of-airlines-make-up-89-caav.html) · [CAAT air-transport statistics](https://www.caat.or.th/en/publications/air-transportation-and-aircraft/air-transportation-statistics/) — accessed 2026-08-10
- [JCAB/MLIT OTP context (Skymark)](https://smart.skymark.co.jp/en/news/detail/1193617_1793.html) — accessed 2026-08-10
- [Cirium SE-Asia OTP report](https://www.cirium.com/thoughtcloud/cirium-southeast-asia-monthly-on-time-performance-reports/) · [VariFlight OTP analytics](https://dataworks.variflight.com/products/data-analysis/) · [OAG OTP](https://www.oag.com/on-time-performance-data) — accessed 2026-08-10
- [AeroDataBox pricing](https://aerodatabox.com/pricing) · [aviationstack pricing](https://aviationstack.com/pricing) · [OpenSky FAQ (non-commercial)](https://opensky-network.org/about/faq) — accessed 2026-08-10
