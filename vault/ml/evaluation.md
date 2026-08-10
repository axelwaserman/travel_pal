---
type: ml
title: Evaluation — Metrics, Backtest Protocol, Promotion Gate
tags: [ml, evaluation, calibration, backtest, gate, brier]
status: draft
updated: 2026-08-08
---

# Evaluation & Promotion Gate

> Metrics, the time-honest backtest, and the bar a model must clear to become champion. Consumes [[problem-framing]] (three tasks), [[model-selection]] (conformal), [[research-summary]] (calibration bar). Feeds [[training-orchestration]] (`evaluate_model` + drift sensor), [[serving-deployment]] (promotion). **No accuracy numbers asserted — all thresholds are TODO, set after the first backtest.**

## Metrics by task (calibration is primary)

| Task | Metrics | Primary |
|---|---|---|
| **T1 cancellation** (binary) | **Brier score**, reliability curve / **ECE**, AUC-PR (rare-event, PR > ROC), log-loss | Brier + ECE |
| **T2 exceedance** `P(delay≥{15,60,180})` | Brier + ECE **per threshold**, AUC-PR | Brier + ECE per threshold |
| **T3 magnitude / band** | **Pinball loss** per quantile, MAE(`expected_delay_min`), **empirical coverage** of `[p10,p90]` vs 80% nominal, mean interval width (sharpness) | Coverage + pinball |

Rationale: [[research-summary]]/[[differentiation-thesis]] make **calibration the product** — a sharp-but-miscalibrated model fails the gate even if MAE is low. Report `calibration.brier` in every §C response ([[feature-contract]]).

## Backtest protocol — time-honest, no leakage

- **Rolling-origin / walk-forward** splits ordered by `flight_date`. Train on `[…, T]`, validate/calibrate on a held-out **future** window `(T, T+Δ]`. **Never random k-fold** (temporal + route autocorrelation → leakage).
- **Respect the BTS ≤3-month lag** in the split so the backtest mimics production data availability ([[feature-contract]] SLA). The model at "booking time" may only see data that would truly have been materialized then.
- **Point-in-time feature correctness:** base-rate aggregates (`hist_*`) computed only from data ≤ split origin; §B weather joined at each flight's actual `observed_at` — no future METAR.
- **Segment the report:** by route sample size (`route_n` buckets — thin routes will be worse), by lead time (booking vs day-of), by season, and **with vs without the `late_aircraft_risk` feature** (quantify what the paid feed would buy — [[features]]).
- **Degradation test:** re-score the day-of set with §B signals masked → confirm calibration still holds under the fallback path ([[serving-deployment]]).

## Promotion gate (champion/challenger)

A newly trained challenger becomes `champion` only if, on the **most-recent held-out window**, it:

1. **Does not regress Brier/ECE** on T1 and each T2 threshold vs the current champion (calibration is the hard constraint).
2. **Holds interval coverage** within tolerance of nominal (e.g. 80% band covers ~80% ± tol — *tol TBD*).
3. **Does not regress pinball loss / MAE** materially.
4. Passes point-in-time + degradation checks above.

Absolute thresholds (min Brier, coverage tol, min AUC-PR) are **TODO — calibrated against the first real backtest and the B2B bar**, not invented here ([[AGENTS]] rule 2). Gate is enforced in the `evaluate_model` Dagster asset; only a pass flips registry `status` ([[training-orchestration]]).

## Drift monitoring (feeds the retrain sensor)

Rolling production monitor on: Brier/ECE, coverage, and feature/prediction distribution (PSI). Sustained breach → Dagster sensor triggers off-cadence retrain ([[training-orchestration]]).

## OPEN — the calibration bar itself (unresolved, cross-team)

**What Brier/reliability level do B2B buyers (P4 insurers, P3 TMCs) actually require, and can lakehouse+BTS+GBM hit it vs FlightAware Foresight?** This is [[research-summary]] OQ3 and [[feature-contract]] OQ2 — **unanswerable without (a) a first backtest and (b) a design partner** ([[research-summary]] OQ2). Until then, the public accuracy story stays qualitative ("calibrated + transparent", per [[differentiation-thesis]] / [[marketing]]) — **never a numeric superiority claim.** `#task/ml 🔺 ⛓ [[research-summary]]`

## Handoff

- → [[training-orchestration]]: gate logic + drift metrics.
- → [[marketing]]: only calibration/coverage framing is publishable, and only once backtested — no accuracy-superiority claim ([[differentiation-thesis]]).

## Sources

- [[research-summary]] (calibration > accuracy; OQ2 design partner, OQ3 calibration bar), [[feature-contract]] §C + SLA, [[differentiation-thesis]] — repo vault, accessed 2026-08-08
- Romano et al. 2019 (CQR coverage), standard forecasting practice (rolling-origin backtest) — public literature, accessed 2026-08-08
