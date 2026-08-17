---
type: roadmap
title: Product Roadmap — v1 MVP and beyond
tags: [roadmap, product, mvp, planning]
status: draft
updated: 2026-08-17
---

# Product Roadmap — v1 MVP and beyond

> Draft for human review. Synthesizes the 7-agent package + follow-up data spikes into a phased plan. **No code** — this is planning only; the `CLAUDE.md` Pre-Code Gate still applies before any implementation.

## Strategy in one paragraph

A **B2C flight-decision power tool** — not a reassurance app. The commercial product serves **one persona, the Decisive Traveler who just wants the right flight picked**: for a route it ranks the options by which will actually get you there on time, on the aircraft you want, with connections intact (anchor stories **US-1 + US-3** below). The lead is the **outcome — the pick** — not the raw probability and not the method; reliability, calibration and transparency are the **engine underneath, not the headline** (raw "will it be late" is commoditized — see [[differentiation-thesis]], [[positioning]]). Acquisition starts with a **free funnel = a rate-limited taste of the core**: up to **3 free reliability-score lookups** for a specific flight, which drives signup; a richer self-serve **"lateness explorer"** (slice on-time stats by airline/route/airport, aimed at a nerdier persona) is a **post-MVP** funnel expansion (**US-6**). Rollout is **free-MVP-first, cost-capped ≤€50/mo**: ship the free product, train models on the data we can legally get, acquire first users, measure interest, and only *then* decide whether to buy commercial feeds ([[decision-docket]] rollout resolution). B2B is docked. Working name **FlightPal**; rename deferred ([[naming]]).

## User stories (locked 2026-08-17)

The product hangs off two anchor stories; the rest are staged. **We are a power tool, not a reassurance tool** — the "just reassure me" story was explicitly dropped.

| #        | Story                                                                                                    | Persona            | Stage                        |
| -------- | -------------------------------------------------------------------------------------------------------- | ------------------ | ---------------------------- |
| **US-1** | As someone booking a trip, I want the option **least likely to be delayed / misconnect** on my route.    | Decisive Traveler  | **MVP anchor**               |
| **US-3** | As a traveler, I want to know **which specific aircraft/cabin** I'll be on.                               | Decisive Traveler  | **MVP anchor (co-lead)**     |
| **US-4** | As someone with a tight connection, I want to know **if leg 1 still makes leg 2** before I book.         | Decisive Traveler  | MVP+                         |
| **US-5** | As someone flying today, I want a proactive **"it's slipping, act now"** alert.                           | Decisive Traveler  | Phase 2 (day-of)             |
| **US-6** | As a data-minded user, I want to **explore lateness stats by airline / route / airport** myself.         | Data Explorer      | Post-MVP funnel (DuckDB-WASM) |
| ~~US-2~~ | ~~As an anxious flyer, I want to be told plainly I'll be fine.~~                                          | —                  | **Dropped — not our voice**  |

- **Commercial product = one persona: the Decisive Traveler** who wants the right flight picked.
- **Acquisition funnel = the Data Explorer** (nerdier) — served *later* by US-6; the MVP funnel is just the rate-limited core (3 free lookups).

## The constraint that shapes everything: the data-fidelity map

Verified across [[regional-data-feasibility]], [[data-sources-apac-me]], [[historical-nonus-sources]]: **US-BTS is the only free, deep, delay-labeled spine on earth.** Each region can only support the product surface its data allows.

| Region                                | Best cheap data (≤€50/mo)               | Depth                                          | Delay label         | Surface it can support                                  | Available             |
| ------------------------------------- | --------------------------------------- | ---------------------------------------------- | ------------------- | ------------------------------------------------------- | --------------------- |
| **US**                                | BTS ASQP (free, public domain)          | deep (10+ yr)                                  | ✅ + cause codes     | full: reliability shopping **and** day-of forecast      | **now**               |
| **EU**                                | AeroDataBox (~€5/mo)                    | none — forward-accrue only (7/14/30-day pulls) | ✅                   | reliability shopping, thin at launch → sharpens monthly | **accrue from day 1** |
| **APAC (AU + IN)**                    | BITRE + DGCA (free, CC-BY)              | deep but **aggregate monthly**                 | ❌ (base rates only) | coarse base-rate reliability shopping                   | **now (coarse)**      |
| **China / Korea / SG / JP / Gulf-ME** | commercial only (Cirium/OAG/VariFlight) | —                                              | —                   | none under budget                                       | **deferred**          |

Non-commercial escape hatches (OpenSky trajectories, Eurocontrol ADRR/CODA) exist but are **research/non-commercial** → usable only for backtesting, never the shipped product.

## Use-case anchor (verified against incumbents — [[competitor-usecase-gap]])

- **A — Pre-booking reliability shopping = THE GAP → anchors the MVP.** No consumer product offers sortable, quantified, multi-criteria reliability shopping; Google only shows a black-box "often delayed" flag. Bonus: it's **batch historical analytics** — no live feed, cheapest to serve, and tolerant of coarse data → widest region reach.
- **C — Day-of foresight = PARTIAL → Phase 2.** Flighty already owns "will it be delayed" ($59.99/yr); only micro-gaps are a fused **"leave-by"** recommendation + cross-platform. Needs paid live feeds.
- **B — Disruption rebooking = TRAP → skip.** A booking-rails/ticketing problem; our wedge adds nothing post-cancellation.

## Phases

### Phase 1 — MVP: US Reliability Route-Shopping (Use Case A)
**Goal:** ship the demand gap on the cheapest possible footprint.
- **Data:** widen the existing BTS ingest projection to pull the delay + cause columns already in the ZIPs ([[data-acquisition-scan]]); rebuild the on-time marts off BTS (they're currently OpenSky-derived = non-commercial — the [[decision-docket]] D1 fix). Free weather history (Iowa IEM ASOS) staged for Phase 2.
- **Model:** `model_us` on **historical/base-rate reliability** features (no live signals yet). LightGBM + conformal; SHAP for the "why". Library-agnostic trainer so LightGBM/XGBoost can be benched on the first backtest ([[model-primer]]).
- **Surface:** the **pick** for a route — **sortable route/carrier reliability** with calibrated odds, the **assigned aircraft/cabin** where known (**US-3**), and SHAP reason codes one tap away (reliability/calibration are the engine, not the headline). Free funnel = a rate-limited taste of exactly this: **up to 3 free reliability-score lookups for a specific flight** → signup. No precise underlying data shipped to the browser ([[frontend-backend-split]]).
- **Infra:** batch-only. No live feed, no streaming, no event bus. Minimal FastAPI serving the recommendation; **DuckDB-WASM is deferred post-MVP** (it's the engine for the US-6 explorer, not the MVP pick). ~€1/mo ([[platform-summary]], [[data-acquisition-scan]]).
- **Advance gate:** real users + measured interest in the reliability pick.

### Phase 1.x — Widen regions cheaply
- **Start AeroDataBox EU accrual on day 1** (data clock is the bottleneck — no backfill exists). EU reliability surface improves monthly as history accrues.
- Add **APAC AU + IN** free aggregate base-rates (coarse reliability shopping; clearly labeled as base-rate, not day-of).
- Same surface, region-partitioned (`model_eu`, `model_apac` on the shared spine). Each region lights up as its data allows; UI communicates fidelity honestly.

### Post-MVP funnel — the "lateness explorer" (US-6)
- A free, self-serve surface to **slice on-time stats by airline / route / airport** for the Data Explorer persona — top-of-funnel that costs ~nothing to serve and feeds signups into the paid pick engine.
- **Powered by DuckDB-WASM over a public subset of the lakehouse** — the one place edge-compute earns its keep ([[frontend-backend-split]], [[differentiation-thesis]] keeps DuckDB-WASM demoted *until here*).
- Deliberately **not in the MVP**: the MVP funnel is just the rate-limited 3-lookup taste of the core pick.

### Phase 2 — Day-of Foresight (Use Case C), gated on proven interest + paid-feed decision
- **Trigger:** Phase 1 shows enough interest to justify spend — this IS the "buy commercial keys?" checkpoint.
- **Data:** live day-of signals — free aviationweather.gov METAR/TAF + FAA NAS Status; AeroAPI spot checks; optional paid live-status feed if justified.
- **Model:** the full calibrated **day-of** LightGBM+conformal with weather + late-aircraft features (US/EU where flight-level data exists; not APAC-free).
- **Surface:** proactive delay forecast + alerts + the **"leave-by"** recommendation (the verified micro-gap vs Flighty) + cross-platform.
- **Advance gate:** calibration bar met on a real backtest before any public accuracy-adjacent claim ([[evaluation]]).

### Deferred / explicitly out of scope
- Disruption rebooking (Use Case B — trap).
- China / Korea / SG / JP / Gulf-ME regions (no data under budget).
- B2B data feed (docked).
- Personal itinerary uploads / multi-tenant (was legacy Phase 2 — reintroduces the security CRITICALs C4/C5; only if a clear need emerges).

## Locked decisions (carried in from [[decision-docket]])
- B2C only; free-MVP-first, ≤€50/mo; two+ regional models on a shared region-partitioned spine; tabular LightGBM/XGBoost + conformal + SHAP (no LLM in the prediction path); warm R2 storage (not Glacier) for training data; no event bus.

## Open forks to close before/within Phase 1
- **Naming:** **FlightPal** retained as working name; rename deferred. Known collision (tryflightpal.com) to resolve before any public/commercial launch; independently-verified alternates on file ([[naming]]).
- **Highcharts non-commercial license** — swap before any commercial framing ([[architecture-summary]]).
- **Security must-fix** for whatever host Phase 1 runs on: C3 (no API key in the browser) is platform-independent and applies even to the free MVP; C1 default-creds is mooted by a managed host ([[security-summary]]).
- **NOAA/FAA + AeroDataBox redistribution terms** — confirm we may serve derived data publicly.

## Success metric spine (how "measure interest" gets concrete)
Define before launch: free-signup → activation (ran a reliability search) → repeat-use → the point at which query-cap friction signals willingness to pay. These numbers gate the Phase 2 spend decision.
