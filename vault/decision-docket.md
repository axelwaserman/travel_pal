---
type: decision-docket
title: Decision Docket — Adversarial Review of the Glasswing/TravelPal Strategy Package
tags: [review, decision, adversarial, go-no-go]
status: draft
updated: 2026-08-08
---

# Decision Docket — What the Human Must Decide

> Adversarial review of the 39-note strategy+architecture package produced by the seven agents. This note does **not** summarize or endorse; it surfaces the forks, contradictions, and unvalidated load-bearing assumptions the human must resolve before any go/no-go. Ranked most-consequential first. Every claim is ground-truthed against the repo where possible; unverifiable ones are marked "unverified" with how to check.
>
> Conflicting notes are wikilinked so you can open both sides. The team ran largely in parallel and **several agents never saw each other's output** — the seams below are where that shows.

---

## Resolutions (session 2026-08-09) — decided by the human after two follow-up spikes

Two data spikes and the human's calls have resolved several of the forks below. The original ranked analysis is retained unchanged for the record; this block is the current state.

- **D1 — RESOLVED (blocker dissolved).** The BTS delay label was never truly absent: the BTS ASQP ZIPs we already download contain `DepDelay`/`ArrDelay`/actual-times **plus** `CarrierDelay`/`WeatherDelay`/`NASDelay`/`LateAircraftDelay`. The current asset just doesn't project them → fix is widening the column projection (free, public-domain, commercial-safe). See `vault/engineering/data-acquisition-scan.md`. The OpenSky-derived on-time marts (the real, verified problem) get rebuilt off the newly-projected BTS delay fields. Free weather history via Iowa IEM ASOS/METAR archive unblocks the day-of model.
- **D2 — RESOLVED into a two-model design.** Not US *xor* EU. **Two separate regional models** — `model_us` (deep free BTS backfill, strong at launch) and `model_eu` (forward-growing AeroDataBox ~€5–30/mo spine, thin at launch, sharpens monthly) — sharing one region-parameterized spine (Dagster orchestration, dbt+DuckDB transforms, Iceberg/R2 storage, FastAPI serving, map+form UI). US-trained weights do NOT transfer to EU; each region trains its own. Monetization hook = EU261/UK261 (EU/UK). See `vault/product/regional-data-feasibility.md`.
- **D5 — RESOLVED.** €50/mo was never the binding constraint — licensing + region were. The full feed+storage stack lands ~€1–6/mo. Storage = warm Cloudflare R2 ($0 egress) for train/test + tiny cold archive; **not** Glacier for training data (slow + per-read fees). `late_aircraft_risk` comes free from BTS cause codes; a paid live feed is deferred, not required for v1.
- **Model stack — RESOLVED.** Regular tabular ML (LightGBM/XGBoost + conformal calibration + SHAP). **Not** an LLM (an earlier "llm server" was a misstatement). An LLM may later narrate results in plain language, but never produces the prediction.
- **D3 — RESOLVED: B2B docked.** The human docked the entire B2B-feed thesis for now. Product is **B2C-only**. The earlier "gate build on a signed B2B design partner" fork is moot.
- **Rollout — DECIDED: free-MVP-first.** Build a free-to-user, cost-capped MVP to (a) train models on quality US (free BTS) + EU (cheap AeroDataBox forward spine) data, (b) acquire first free users, (c) measure interest, THEN decide whether to buy richer commercial API keys (Cirium/OAG). Spend stays under the €50/mo cap. Recommendation pending human confirm: **start AeroDataBox EU forward-accrual now** — EU history only grows forward and cannot be cheaply backfilled, so the data clock is the binding constraint.
- **Region scope — EXPANDING (research in flight).** Beyond US/EU: `staff-product-engineer` scanning APAC + Middle East data sources (`vault/engineering/data-sources-apac-me.md`) to see which regions have quality data under budget. Region stays a partition dimension on the shared spine.
- **MVP use cases — research in flight.** `product-researcher` deep-diving three B2C use cases (pre-booking route-shopping / disruption rebooking / day-of delay foresight) vs incumbents (Flighty, Google Flights, TripIt, Hopper, airline apps) to find the defensible gap and pick the MVP anchor (`vault/product/competitor-usecase-gap.md`).
- **Still open:** D6 (rename to Glasswing — TM/domain checks unrun), D7 (Highcharts non-commercial license swap; NOAA/FAA + AeroDataBox redistribution terms), and the ADRR **R&D-only license risk** if used to train a commercial EU model — verify before it's load-bearing.

---

## D1 — What is v1, really? The delay label does not exist, and the "free on-time wedge" is built on non-commercial data.

**Decision:** Accept that v1 is a **cancellation-rate + base-rate product** (no "how long will it be delayed"), OR spend the ingest/backfill work to make the *predict-how-long* and *on-time route-shopping* value props real before launch.

> **→ Human directive (2026-08-10):** Yes — **backfill US now** (delay columns already in the BTS ZIPs, just widen the projection) **while EU accrues forward via daily ingestion**. The two run in parallel: US gets real depth immediately; EU builds a dataset from day-1 forward-looking pulls. See Resolutions (top) + [[data-acquisition-scan]].

**Why it's forced (ground-truthed, not taken on faith):**
- The BTS spine carries **no delay field**. `pipeline/pipeline/assets/bts_on_time.py` `_SCHEMA` and `stg_bts_on_time.sql` contain only `flight_date, carrier, tail, flight_number, origin, dest, crs_dep_time(string), cancelled, cancellation_code, diverted, year_month`. There is **no `DepDelay`/`ArrDelay`/elapsed-time**. ML flagged this correctly and bluntly in [[features]] gap #1 and [[problem-framing]] — **CONFIRMED**.
- The **only** delay signal in the repo, `fct_flight_performance.delay_minutes` / `is_on_time`, is an **OpenSky block-time-vs-route-median proxy** (`fct_flight_performance.sql` reads `stg_flights` = OpenSky `icao24/callsign`). OpenSky is **non-commercial** ([[ingestion-backfill]], [[architecture-summary]] dec. 2). CONFIRMED.
- **New finding the team missed:** the two "on-time / timeliness" marts that feed the *free edge wedge* — `agg_route_timeliness.sql` and `agg_daily_timeliness.sql` — **both `ref('fct_flight_performance')`**, i.e. OpenSky-derived. Only `agg_route_cancellations` and `agg_carrier_cancellations` read `stg_bts_on_time` (BTS, public-domain). So [[frontend-backend-split]]'s claim "Safe to make public because BTS is public domain" is **false for the on-time surfaces today** — the route-reliability/on-time-ratio/"Delay Almanac" surfaces are currently non-commercial OpenSky aggregates. The *cancellation* surfaces are the only commercially-clean free content that exists.

**Consequence:** the delay-field gap blocks the **paid** prediction (T2/T3 can't train — ML says so) *and* the transparency-wedge **free** on-time route-shopping ([[positioning]], [[messaging]], [[lead-gen-plan]] "Delay Almanac") *and* marketing's entire "Know which flight to trust" promise. Both tiers currently rest on data that either doesn't exist (BTS delay) or can't be sold (OpenSky).

**Options:**
- **A. Honest v1 = cancellation + base-rate only.** Ship what BTS legally supports today: cancellation rates by route/carrier + booking-time base rates. Kills the "predict how long / on-time route-shopping" story until the BTS On-Time *delay* columns are ingested. This is exactly the fallback ML and [[research-summary]] already name. Cheapest, most honest; guts the marketing headline.
- **B. Extend BTS ingest to the full On-Time Performance delay fields + historical METAR backfill, then launch.** Makes the real product possible. Cost: real ingest/backfill/point-in-time-weather work (ML gaps #1–#3), and it gates everything downstream (training, calibration, the B2B feed, the methodology page). Weeks, not days. **→ Human directive (2026-08-10): backfill the delay column FIRST — it's the highest-leverage first step and unblocks the model.**
- **C. Buy a commercial feed** (Cirium/AeroAPI/commercial OpenSky) for delay+freshness. Solves data but **blows the $0 cost-structure wedge** that is the entire differentiation thesis (see D5).

**Reviewer's read:** Do **B** (extend BTS On-Time delay ingest — it's public-domain and already the spine source) and rebuild the on-time marts off BTS *before* any commercial launch, but **ship A's cancellation-only surface first** as the honest free wedge. Do **not** let marketing publish "know which flight to trust / on-time" copy until the BTS-derived on-time marts exist. **Confidence: high** on the diagnosis (verified in-repo); medium on B-then-A sequencing. Changed by: evidence the BTS On-Time prezip actually exposes the delay columns at the projection step (very likely — it does in the real BTS dataset; the current asset simply doesn't select them).

---

## D2 — EU-first GTM vs a US-only data spine.

**Decision:** Launch **US** (where the data is) or **EU** (where the money/action-economics are) — you cannot currently do both.

**Why it's forced:** [[research-summary]] finding 5, [[positioning]], [[privacy-compliance]] and [[marketing-summary]] **all lean EU** (EU261 economics, withdrawn US DOT compensation rule, GDPR-first, insurance angle). But [[ingestion-backfill]] §0 and [[differentiation-thesis]] §"cannot win" state the spine is **BTS = US-only**, and OpenSky "thins outside EU/US." **There is no EU flight-reliability data in the design.** The market with the better action-economics is the market with no product behind it. These two conclusions were written by different agents and never reconciled.

**Options:**
- **A. US launch.** Data-aligned. Weaker monetization (no EU261; US has refunds, not fixed payouts). Marketing's insurance/affiliate angle mostly evaporates.
- **B. EU launch.** Requires a **paid global/EU feed** (see D5) on day one — kills the $0 wedge and adds COGS not in any model. **→ Human directive (2026-08-10): launch EU only once forward-looking daily ingestion (start ASAP) has accrued a big-enough dataset — not gated on a paid feed, gated on the accrual clock. Start the AeroDataBox EU accrual immediately so that clock is already running.**
- **C. US free wedge now, EU as a funded Phase 2** once a paid feed is budgeted.

**Reviewer's read:** **C.** The honest free US cancellation wedge (D1-A) is the only thing shippable at $0, and it's US-data-native. Treat EU as gated on a paid feed + a signed insurer. **Confidence: high** the contradiction is real; medium on sequencing.

---

## D3 — Is there a buyer? "B2B feed is the margin" is unvalidated and circularly gated.

**Decision:** Gate the whole build on signing **one** B2B design partner first, or proceed on the hope that the feed sells.

**Why it's forced:** Every summary ([[research-summary]], [[pricing-summary]], [[tier-matrix]], [[product-shape-by-tier]], [[differentiation-thesis]]) pivots the business to "**the margin is the B2B auditable feed**." Yet:
- **No design partner is signed** — [[research-summary]] OQ2, [[pricing-summary]] open Q, [[unit-economics]] risk #4 all admit it.
- API prices ($0.003–0.006/LP, $99/$1,000 mins) are explicitly **"estimated"/"assumed"** ([[tier-matrix]]).
- The B2B wedge is **calibration/auditability**, but [[evaluation]] + [[ml-summary]] concede the calibration bar vs Foresight is **"unanswerable without (a) a first backtest and (b) a design partner."**
- **Circular chain:** can't set the price without a partner → can't win a partner without a calibrated, auditable feed → can't calibrate without the delay label (**D1**) → can't publish the methodology page marketing's transparency wedge depends on. The margin story sits at the end of a dependency chain whose first link (D1) is broken.

**Options:**
- **A. Partner-gated build.** Sign (or get a signed LOI from) one TMC/insurer before building the B2B surface. De-risks the whole pivot; slows it.
- **B. Build free wedge, defer B2B.** Ship the consumer free tier; treat B2B as opportunistic. Concedes the margin story is speculative.
- **C. Build B2B on spec.** Highest risk; contradicts the team's own "validate before over-investing."

**Reviewer's read:** **A.** The team itself flags this as the validation gate; honor it. A single design partner also resolves the calibration-bar unknown and the pricing guesswork at once. **Confidence: high.** Changed by: an inbound buyer signal, which none of the notes present.

> **→ Human directive (2026-08-10): forget B2B for now — focus B2C.** This whole decision (D3) is moot for the MVP. B2B is docked; see Resolutions (top). Revisit only if an inbound buyer appears.

---

## D4 — Deployment target: the compose stack vs the Cloudflare+Fly stack — and which one the threat model actually applies to.

**Decision:** Pick the launch target platform, because **security and platform threat-modeled two different systems and never synced.**

**Why it's forced (the sharpest cross-agent contradiction):**
- [[security-summary]]/[[threat-model]] rank **C1 (CRITICAL): default `admin/admin` + open Nessie/PG/S3**. **CONFIRMED in-repo** — `docker-compose.yml` publishes 5432/19120/9333/8080/8888/8333/3000 and defaults `SEAWEEDFS_ACCESS_KEY:-admin`; `.env.example` sets `admin/admin` and `s3.configure -user=anonymous ... -actions=Read,List`. Real, against the compose posture.
- But [[platform-summary]]/[[orchestration-storage]] **propose deleting exactly that stack**: SeaweedFS(4)+Nessie→**R2 + R2 Data Catalog**, Postgres→**Neon**, all managed. If adopted, **C1 as written is moot** — there is no self-hosted SeaweedFS/Nessie with `admin/admin` to attack. The residual risk becomes **R2 API-token scoping + Neon/Upstash secret hygiene**, which platform explicitly left as "**assumed — please write `vault/security/` and flag conflicts**."
- **Both notes open with a warning that the other's folder "does not exist yet."** The charter's mandated "security ↔ platform sync" **did not happen.** Security hardened a stack platform wants to retire; platform assumed a security posture security never reviewed.
- **C3 (API key in browser)** and **C2 (artifact load)** are app-layer and **survive on either platform** — see Verified/Debunked.

**Options:**
- **A. Migrate to Cloudflare+Fly, then re-run the threat model against it.** C1/H1/H3/H11 (compose-network findings) largely dissolve; new R2/Neon/Upstash token-scoping controls must be specified. Cost: depends on **R2 Data Catalog, which is public beta** (billing enabled 2026-08-03 — 5 days before this review; [[platform-summary]] flag #1, [[orchestration-storage]] beta box). Fallback = self-host Nessie, which **reintroduces a container and part of the C1 surface**.
- **B. Ship on hardened compose.** C1–C5 + H-series become real, binding, and must all be fixed (secrets, TLS, drop anon `List`, split public/private buckets). More ops, more attack surface, but no beta dependency.

**Reviewer's read:** **A**, but do not treat C1 as "done by migrating" — force platform+security to co-author one note reconciling R2 token scoping, anon-read bucket split, and secrets before provisioning, and **confirm R2 Data Catalog GA/SLA** (or commit to the Nessie fallback and its C1 residue) before paid launch. **Confidence: high** the sync gap is real (both notes admit it). Changed by: a platform decision to stay on compose, which flips every mooted CRITICAL back on.

---

## D5 — Paid live feed: freshness vs the $0 cost wedge.

**Decision:** Budget a commercial live-status feed (enables day-of, freshness, the strongest `late_aircraft_risk` feature, EU/global) **or** ship stale-US-BTS-only and drop the day-of/fresh story.

**Why it's forced:** The `late_aircraft_risk` feature is called "the single strongest published delay driver" ([[features]] §B) yet is **paid-feed-gated** because OpenSky is non-commercial. [[ingestion-backfill]] OQ, [[unit-economics]] risk #3, [[architecture-summary]] OQ1, and [[platform-summary]] flag #3 all name this as an unresolved gate. A paid feed adds COGS **not in any current model** and raises the LP cost floor — directly threatening the "$0.002/LP ceiling" and the free-edge cost wedge that is the entire [[differentiation-thesis]].

**Options:** **A.** Stale-US-BTS-only MVP (no day-of magnitude; degrade-to-cached is the norm, not the exception). **B.** Budget Cirium/AeroAPI/commercial-OpenSky (unlocks day-of + EU/global; blows $0 wedge; needs re-pricing per [[unit-economics]] risk #3). 

**Reviewer's read:** **A for v1** (consistent with D1-A/D2-C), revisit B only after a design partner (D3) proves the day-of feature pays for the feed. **Confidence: high.**

---

## D6 — Rename TravelPal → Glasswing.

**Decision:** Adopt "Glasswing" now, or defer until the transparency wedge it names is actually real.

**Why it's forced:** [[naming]]/[[marketing-summary]] recommend Glasswing because its glass-box metaphor *is* the transparency wedge. But (a) **every trademark/domain/app-store/social check is explicitly unrun** ("NONE verified here" — [[naming]]); and (b) the transparency promise is only defensible once the **published backtest/methodology page exists**, which is gated on D1+D3. Branding the company after a capability you can't yet demonstrate is a soft risk, but a real one.

**Options:** **A.** Adopt now, run the (blocking) legal/domain checks first. **B.** Keep working name until D1 makes the methodology page real, then rename at launch. **C.** Pick a warmer fallback (Truebound/Almanac) if consumer-tone wins over B2B-nerd tone.

**Reviewer's read:** **A** on the name (it's the strongest of the seven and on-thesis), but **do not ship transparency marketing until the backtest is real** ([[evaluation]] gate). Run the trademark search before any spend. **Confidence: medium** — this is judgment, not a blocker.

---

## D7 — Free-edge legal gates: Highcharts + NOAA/FAA redistribution.

**Decision:** Confirm the free edge is legally shippable before public launch.

**Why it's forced:** `LICENSING.md` + [[architecture-summary]] dec. 9 + [[frontend-backend-split]] OQ: **Highcharts is non-commercial-licensed** and "MUST be replaced (ECharts/uPlot) before any commercial/paid/ad-funded launch." Separately, [[ingestion-backfill]] marks **NOAA/FAA redistribution terms as "assumed, verify"** — the free edge redistributes those signals. Both are cheap to resolve but are hard launch gates, not backlog.

**Reviewer's read:** Swap Highcharts and verify gov-feed redistribution before the free tier goes public. **Confidence: high** (verified in `LICENSING.md`). Low effort, non-negotiable.

---

## Verified / Debunked (claims fact-checked against the repo)

| Claim | Source note | Verdict |
|---|---|---|
| "BTS spine has no delay label" | [[features]], [[problem-framing]] | **CONFIRMED** — `bts_on_time.py _SCHEMA` + `stg_bts_on_time.sql` carry only cancelled/diverted/route/carrier/date, no Dep/ArrDelay. |
| "Only delay signal is an OpenSky non-commercial proxy" | [[features]], [[architecture-summary]] | **CONFIRMED** — `fct_flight_performance.sql` = block-minutes vs route median off `stg_flights` (OpenSky). |
| "Free edge on-time surfaces are safe public-domain BTS" | [[frontend-backend-split]] | **DEBUNKED (partly)** — `agg_route_timeliness`/`agg_daily_timeliness` read `fct_flight_performance` (OpenSky, non-commercial). Only the two `*_cancellations` marts are BTS-derived. New finding; team missed it. |
| Security C1: default creds + open ports | [[threat-model]], [[security-summary]] | **CONFIRMED** against `docker-compose.yml` + `.env.example`. But **mooted** if platform's R2/Neon migration (D4) is adopted — neither agent reconciled this. |
| Security C2: model-artifact **pickle** RCE | [[threat-model]] TB6 | **PARTLY DEBUNKED** — ML chose **native LightGBM `model.txt`, not pickle/joblib** ([[serving-deployment]]). Boot-load RCE-via-pickle premise doesn't hold; residual risk is model-swap/data-poison via bucket write, so the signing/write-restriction control still stands at lower severity. |
| Security C3: API key in browser | [[access-control]] A1 | **CONFIRMED & platform-independent** — survives on Cloudflare+Fly; an app-layer auth decision. |
| Platform break-even "~5–15 Plus subs" vs fixed infra $17–50/mo | [[cost-model]], [[unit-economics]] | **RECONCILES** — 5–15 × $3.25/mo ≈ $16–49 ≈ $17–50. Internally consistent. |
| Platform per-LP ≈ $0 doesn't threaten the $0.002/LP ceiling (that's weather COGS) | [[cost-model]], [[unit-economics]] | **RECONCILES** — cost partition is clean; 50k LP → $25–75/mo weather COGS matches unit-econ blended $0.0005–0.0015. |
| R2 "zero egress" | [[platform-summary]], [[orchestration-storage]] | **PLAUSIBLE/TRUE** (R2 genuinely waives egress) but **R2 Data Catalog is public beta** — the ~$0 *catalog* + "7 containers→1" claim is beta-dependent; fallback reintroduces a Nessie container. |
| Backfill "72M rows / 4.8 GB / 30–90 min at 8-way" | [[ingestion-backfill]] §1.2, [[architecture-summary]] | **UNVERIFIED / optimistic** — all "estimated"; BTS transtats server-side ZIP generation is slow/flaky. Verify by timing 3–5 real monthly pulls before trusting the wall-clock. |
| Highcharts non-commercial; must swap before paid | `LICENSING.md`, [[architecture-summary]] dec.9 | **CONFIRMED** in `LICENSING.md`. |
| "89.3% / MIT Lincoln Lab / 7.2B records" Google stat | [[competitors]], [[research-summary]] | Correctly self-flagged **likely fabricated**; team already refuses to cite it. Good. |

---

## Weakest links (the 3 assumptions most likely to sink this if wrong)

1. **That the BTS On-Time delay columns can be cheaply ingested to resurrect the "predict how long" + on-time wedge (D1).** If the delay fields turn out costly/unavailable at the needed grain, v1 collapses to a cancellation-rate tool and the entire "Know which flight to trust" positioning is unshippable. *Verify:* pull one real BTS On-Time prezip and confirm `DepDelay`/`ArrDelay`/`CRSDepTime` project cleanly into the existing asset. This is the linchpin — D1, D2, D3, D5, D6 all hang off it.
2. **That a B2B buyer exists at the assumed price and calibration bar (D3).** The whole margin thesis is unvalidated, the prices are guesses, and the calibration bar vs Foresight is admittedly unknown. If no TMC/insurer signs, the product is a free consumer tool with negative unit economics and no revenue engine. *Verify:* one signed design partner or LOI before building the B2B surface.
3. **That the $0 cost-structure wedge survives contact with reality (D4+D5).** It depends on: R2 Data Catalog going GA (public beta today), NOAA/FAA redistribution being free-to-redistribute (unverified), no paid feed being required (D5), and DuckDB-WASM HTTP Range working on R2 ([[platform-summary]] flag #2, still an untested blocking `curl -r`). Any one failing raises the cost floor and erodes the only durable differentiator. *Verify:* the three blocking platform tests + gov-feed terms before committing the architecture.
