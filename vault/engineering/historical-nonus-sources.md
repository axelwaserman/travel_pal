---
type: engineering
title: Historical Non-US Flight Data — Verification
tags: [engineering, data, historical, backfill, license, otp, verification]
status: draft
updated: 2026-08-10
---

# Historical Non-US Flight Data — Verification

> Is there any deep, delay-labeled, commercial-clean, ≤€50/mo historical source for EU/APAC — or does "non-US = forward-only OR coarse OR non-commercial" hold? Consumes [[data-acquisition-scan]], [[data-sources-apac-me]]. Feeds [[regional-data-feasibility]], [[ingestion-backfill]].

> [!important] Bottom line — the conclusion HOLDS
> **No source is deep + delay-labeled + commercial-clean + ≤€50/mo for EU or APAC.** Every candidate fails ≥1 of the four. You get to pick **at most three**: deep, cheap/commercial-clean, or delay-labeled. The delay label is the recurring casualty — most cheap/deep non-US data is **raw trajectories** from which delay must be **derived against a separate (paid) schedule reference**.

## The two distinctions that decide everything

- **(i) OTP label vs derived:** BTS gives a true delay label (scheduled vs actual + cause codes). Trajectory sources (ADS-B) give only `firstseen`/`lastseen` positions → delay must be **derived**, and that needs a **scheduled-time reference you don't get in the same feed**. Origin/dest are themselves *inferred* from the trajectory (error-prone).
- **(ii) License:** commercial-use allowed y/n. Research/non-commercial licenses are a **dead end for a paid product**.

## Verified sources

| Source | Depth | Coverage | Label? | License (commercial) | Cost | Verdict |
|---|---|---|---|---|---|---|
| **OpenSky Trino/Impala history** | **2016→ unlimited** (nothing pre-2013) | **EU + US good; Asia/ME thin** | ❌ state-vectors → **derive** delay | ❌ **research/gov/non-profit only; commercial needs a license** (measured) | free (research) | **Dead end for paid product.** Confirms repo `fct_flight_performance` (derives delay vs route-median block) is non-commercial-only. |
| **OpenSky Zenodo COVID dump** | 2019–2022 (frozen) | Global (2500+ receivers), same EU/US bias | ❌ origin/dest + first/last seen only, **no schedule → no delay label** | ✅ **CC-BY** (commercial OK w/ attribution) (measured) | free | The one **commercial-clean deep-ish** set — but **stale + trajectory-only**. Backtest base rates at best. |
| **ADS-B Exchange** | 10-yr backfill **subscribers-only, enterprise annual** | Global ADS-B | ❌ trajectories → derive | ⚠️ RapidAPI tier commercial-ambiguous; commercial = enterprise | RapidAPI $10/mo/10k; deep = enterprise | Deep history paywalled; still no label. |
| **Flightradar24 API** | historical tracks; **deep bulk = "data services" licensing agreement** (enterprise) | Global ADS-B | ⚠️ tracks; sched/actual exists but label depth at low tier *assumed* | ✅ commercial (licensing agreement applies) | **Explorer $9/mo/30k** → Essential $99 → Advanced $900 (measured) | **$9 tier fits budget** but is tracks/recent; deep labeled bulk = enterprise licensing. |
| **AeroDataBox** | **per-request 7-day (Basic/Pro) / 14 (Ultra) / 30 (Mega)** windows — *not* a deep archive | Global | ✅ status + actual times + delay stats | ✅ commercial | ~$5/mo | **Correction: shallow, not "±365-day."** Forward/recent-oriented; **not deep backfill.** |
| **OAG** / **Cirium** | deep, flight-level, delay-labeled | Global incl EU/APAC/China | ✅ true OTP + cause | ✅ commercial | **enterprise ≫ €50/mo** (measured: quote-only) | The only deep+labeled option — **priced out.** |
| Academic (Harvard Dataverse, Kaggle) | one-off, mostly **US/DOT re-hosts** or small EU slices; often stale | varies | mixed; frequently research-only | ⚠️ often research/CC-NC | free | No maintained, global, commercial-clean, labeled set (*assumed* after scan). |

## The unavoidable catch (delay-derivation)

Even the **CC-BY OpenSky Zenodo** data (the only deep-ish commercial-clean option) yields **no delay label on its own** — you must join a **scheduled-departure reference**, and clean schedule history for EU/APAC comes from **OAG/Cirium (enterprise)**. So the cheap path (derive delay from trajectories) is gated by an expensive schedule feed. That is the structural wall.

## Answer to the gating question

- **Deep + labeled + commercial + ≤€50/mo for EU/APAC: does not exist.** (measured across all candidates above)
- **Closest commercial-clean deep option:** OpenSky Zenodo (CC-BY) — but trajectory-only, no label, EU-biased, frozen at 2022.
- **Cheapest commercial labeled:** AeroDataBox (~$5) / FR24 Explorer ($9) — but **shallow/recent**, not deep backfill.
- **Deep + labeled:** OAG/Cirium only — **enterprise, out of budget.**

→ The **"non-US = forward-only OR coarse OR non-commercial"** conclusion from [[data-sources-apac-me]] **stands, verified.** Roadmap implication: US-BTS remains the only free deep delay-labeled spine; EU/APAC historical is either a non-commercial backtest (OpenSky) or a funded enterprise buy. `model_us` trains on real depth; non-US models stay coarse/base-rate until a paid schedule+OTP feed is budgeted → [[regional-data-feasibility]].

## Open questions
- [ ] Would FR24 Explorer ($9/mo) historical tracks yield a usable derived delay label at that tier, or is depth/label gated to enterprise data-services? Verify with a trial. `#task/eng 🔼`
- [ ] Is OpenSky Zenodo (CC-BY, 2019–22) worth ingesting purely for a commercial-clean EU **backtest** base-rate spine? `#task/eng ⛓ [[staff-ml-engineer]]`

## Sources
- [OpenSky Trino history docs](https://openskynetwork.github.io/opensky-api/trino.html) · [OpenSky data/license](https://opensky-network.org/data) · [OpenSky FAQ (commercial license required)](https://opensky-network.org/about/faq) — accessed 2026-08-10
- [OpenSky Zenodo COVID dataset (CC-BY)](https://zenodo.org/records/5815448) · [dataset paper (ESSD)](https://essd.copernicus.org/preprints/essd-2020-223/essd-2020-223-manuscript-version3.pdf) — accessed 2026-08-10
- [ADS-B Exchange RapidAPI](https://rapidapi.com/adsbx/api/adsbexchange-com1/pricing) · [ADS-B Exchange enterprise data](https://www.adsbexchange.com/products/enterprise-api/) — accessed 2026-08-10
- [Flightradar24 API pricing/credits](https://fr24api.flightradar24.com/subscriptions-and-credits) · [FR24 data services](https://www.flightradar24.com/commercial-services/data-services) — accessed 2026-08-10
- [AeroDataBox flight-history (per-request window limits)](https://aerodatabox.com/flight-history/) · [pricing](https://aerodatabox.com/pricing) — accessed 2026-08-10
- [Cirium OTP FAQ](https://www.cirium.com/resources/on-time-performance/on-time-performance-faq/) · [OAG OTP](https://www.oag.com/on-time-performance-data) — accessed 2026-08-10
