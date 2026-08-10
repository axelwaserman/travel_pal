---
type: ml
title: Problem Framing — Delay Prediction as Coupled Tasks
tags: [ml, framing, calibration, targets]
status: draft
updated: 2026-08-08
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

## Architecture decision: quantile-distribution + separate cancel head (NOT a cascade)

- **Rejected — two-stage cascade** (classify delayed → regress if delayed): compounds calibration error across stages and the second stage trains on a censored subsample. Harder to keep the shown probability honest.
- **Recommended — model the conditional delay distribution directly** via multi-quantile regression (T3), then **read T2 exceedance probabilities off the predicted CDF** *and* cross-check with direct threshold classifiers; **T1 cancellation as an independent calibrated binary model.** This yields band + exceedance from one coherent distribution → internal consistency (p_delay_60 ≤ p_delay_15 by construction if quantiles are monotone). See [[model-selection]] for the estimator.
- **Calibration is a first-class output, not a post-hoc nicety** — [[research-summary]] finding 3 + [[differentiation-thesis]] make honesty the wedge. Wrap with conformal (see [[model-selection]], [[evaluation]]).

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
