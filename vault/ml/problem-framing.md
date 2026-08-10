---
type: ml
title: Problem Framing — Delay Prediction as Coupled Tasks
tags: [ml, framing, calibration, targets]
status: draft
updated: 2026-08-10
---

# Problem Framing

> Precise statement of *what we predict* before *how*. Consumes [[feature-contract]] §C (required output), [[research-summary]] (calibration > accuracy), [[personas]] (usefulness bar), [[differentiation-thesis]] (we do NOT out-predict Foresight). Feeds [[model-selection]], [[evaluation]].

## The prediction is three distinct random processes, not one

| Task | Target | Why separate |
|---|---|---|
| **T1 — Cancellation** | `cancel_prob = P(cancelled)` | A cancelled flight has **no delay minutes**; BTS records it as a distinct event (`cancelled`, `cancellation_code`). Mixing it into a delay regressor corrupts both. Separate calibrated binary classifier. |
| **T2 — Delay exceedance** | `p_delay_{15,60,180} = P(delay ≥ t \| operated)` | The [[feature-contract]] §C headline output. Threshold probabilities users/insurers act on. |
| **T3 — Delay magnitude** | `expected_delay_min`, `delay_p10_min`, `delay_p90_min` (conditional on operated) | The uncertainty band. Quantiles, not a point. |

**Composition rule:** unconditional exceedance shown to the user = `P(operated)·P(delay≥t\|operated) + P(cancelled)·1[cancel counts as ≥t]`. Decide with [[sales]]/[[product-researcher]] whether a cancellation counts as "delayed ≥180" for display — proposed: surface `cancel_prob` separately (personas P2/P4 treat cancellation as its own risk).

> **Confirmed (review 2026-08-10): cancellation (T1) is modeled as its own standalone binary classifier**, never folded into the delay heads. Rationale: it's a different physical process, its own BTS event + cause code, and a cancelled flight has no delay magnitude to regress. T1, T2/T3, and T4 (below) are trained and calibrated independently, then merged only at serve time.

## Architecture decision: quantile-distribution + separate cancel head (NOT a cascade)

- **Rejected — two-stage cascade** (classify delayed → regress if delayed): compounds calibration error across stages and the second stage trains on a censored subsample. Harder to keep the shown probability honest.
- **Recommended — model the conditional delay distribution directly** via multi-quantile regression (T3), then **read T2 exceedance probabilities off the predicted CDF** *and* cross-check with direct threshold classifiers; **T1 cancellation as an independent calibrated binary model.** This yields band + exceedance from one coherent distribution → internal consistency (p_delay_60 ≤ p_delay_15 by construction if quantiles are monotone). See [[model-selection]] for the estimator.
- **Calibration is a first-class output, not a post-hoc nicety** — [[research-summary]] finding 3 + [[differentiation-thesis]] make honesty the wedge. Wrap with conformal (see [[model-selection]], [[evaluation]]).

## T4 — Root-cause prediction & the lead-time split (review 2026-08-10)

**Feasibility: yes, but only as a *probabilistic mix*, not a single certain cause.** BTS tags each delayed flight with minutes attributed to five buckets — **carrier, weather, NAS (national-airspace/ATC), late-aircraft, security**. That gives clean training labels, so **T4 = multilabel classification** (predict a probability per bucket; several can co-occur) — same LightGBM recipe. It also *powers* `reason_codes[]` and cross-checks the SHAP attributions ([[features]], [[model-selection]]).

**Predictability differs sharply by bucket — and that maps onto lead time:**

| Cause bucket | Predictable at booking (base-rate, §A only)? | Predictable day-of (§B fresh)? |
|---|---|---|
| **Carrier / structural** (schedule tightness, aircraft rotation, hub congestion) | **Yes** — structural, shows up in historical base rates well ahead | stable |
| **NAS / ATC** (volume, runway config) | partly (seasonal/time-of-day patterns) | sharpened by GDP/ground-stop signals |
| **Weather** | only as a seasonal base rate | **only** sharpens with day-of METAR/TAF (§B) |
| **Late-aircraft** (delay propagation) | weak historically | **needs live inbound status** — paid-feed-gated, non-commercial OpenSky excluded |
| **Security** | rare, near-noise | not meaningfully predictable |

**So a lead-time split IS modelable and is exactly our booking-vs-day-of design:** structural/carrier/NAS causes surface **well ahead** and live in the free base-rate model; **weather + late-aircraft manifest last-minute** and only sharpen in the day-of model with fresh signals (late-aircraft only if a paid feed is budgeted). Honest framing: at booking we predict the *structural* causes with confidence and flag weather/late-aircraft as base-rate priors + wide bands; day-of we tighten them. **No number asserted until backtested.** Data dependency ⛓ [[features]] gaps: the BTS cause-minute columns must be ingested (they are part of the delay-column backfill).

## Threshold & label conventions

- **On-time = delay ≤ 15 min** — align with the existing `fct_flight_performance.is_on_time` (`block_minutes − route_median ≤ 15`) and the BTS/industry 15-min convention. Exceedance thresholds **{15, 60, 180}** min per [[feature-contract]] §C.
- **Label source is a binding open problem** — see ⛓ below. The commercial label must be **BTS-derived arrival/departure delay**, not the OpenSky block-time proxy currently in `fct_flight_performance` (OpenSky is non-commercial — [[architecture-summary]] decision 2).

## Two serving regimes = two feature sets, same targets

Per [[feature-contract]]: **booking-time (base rate, §A only, stale-OK)** and **day-of (§A+§B fresh, ≤minutes)**. Same T1/T2/T3 targets; different inputs and different calibration reference set. Drives the two-artifact design in [[serving-deployment]].

## What "useful" means (bar, not a promise)

Per [[personas]] P1/P4 and [[research-summary]]: **a well-calibrated 70% beats an opaque 95%.** Success is *reliability of the stated probability* (Brier/ECE, interval coverage), plus a `reason_codes[]` explanation — NOT beating FlightAware Foresight on raw accuracy. Targets set in [[evaluation]]; **no numbers asserted until backtested.**

## ⛓ Mismatch flagged back to [[staff-product-engineer]]

The current BTS spine cannot produce the delay label these tasks need — this blocks T2/T3 training. Full detail in [[features]] §"Contract gaps". `#task/ml 🔺 ⛓ [[feature-contract]]`

## Sources

- [[feature-contract]] §C, [[research-summary]] (calibration bar), [[personas]] P1/P4, [[differentiation-thesis]] — repo vault, accessed 2026-08-08
- Repo: `pipeline/transforms/models/intermediate/fct_flight_performance.sql` (≤15-min on-time convention, OpenSky-derived) — accessed 2026-08-08
