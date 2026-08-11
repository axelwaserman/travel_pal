---
type: ml
title: Features — ML Mirror of the Feature Contract
tags: [ml, features, contract, freshness, gaps]
status: draft
updated: 2026-08-08
---

# Features — ML view of the [[feature-contract]]

> The model's input contract, mirrored from [[feature-contract]] (product-eng owns materialization; ML owns *use*). Records agreement + **flags binding gaps** back to [[staff-product-engineer]]. Feeds [[model-selection]], [[training-orchestration]], [[serving-deployment]].

## Agreement with [[feature-contract]]

ML **accepts** the §A/§B/§C tables as the interface. Grain `(carrier_iata, origin, dest, dep_hour_bucket, day_of_week, month)` is correct for base rates. §C output fields match [[problem-framing]] T1/T2/T3. The batch/online split (product-eng precomputes §A base-rate predictions; online adds the §B fresh delta) is accepted and shapes [[serving-deployment]].

## §A historical — model use & encoding

| Feature | ML treatment |
|---|---|
| `carrier_iata`, `origin`, `dest` | **native LightGBM categorical** (high cardinality — no one-hot). Confirm encoding contract with eng. |
| `dep_hour_bucket`, `day_of_week`, `month`, `season` | categorical/ordinal; cyclical where useful |
| `hist_on_time_ratio`, `hist_cancel_rate`, `hist_delay_p50_min`, `hist_delay_p90_min` | numeric priors; **leakage risk** — must be computed from the *training window only*, point-in-time (see [[training-orchestration]]) |
| `route_n` | numeric; also drives `confidence` + conformal band width; enforces `n≥30` coarsening |
| `origin_congestion_idx`, `dest_congestion_idx`, `carrier_reliability_idx` | numeric; NULL→neutral per contract |
| holiday/event flag | **requested add** — derive from a holiday calendar; strong seasonal factor per [[problem-framing]]. `#task/ml` |

## §B fresh (day-of only) — degradation is part of the model

| Feature | ML treatment / fallback |
|---|---|
| `origin_metar_{wind,vis,ceiling,precip_flag}` | numeric; if `stale` → impute training-mean ("benign") + widen band via conformal, never silently use stale ([[feature-contract]] freshness rule) |
| `origin_taf_risk`, `dest_taf_risk` | numeric risk score at ETD |
| `gdp_active`, `ground_stop` | boolean; absent→assume none + lower `confidence` |
| `late_aircraft_risk` | **paid-feed-gated (OpenSky non-commercial).** Model must train & serve **without** it; treat as optional column, imputed-off when unavailable. It is the single strongest published delay driver — note the accuracy left on the table. |

**Training/serving consistency:** the day-of model is trained with §B present; the *same* imputation+widening path used at serve time when signals are stale must be applied at train time (mask-and-impute augmentation) so calibration holds under degradation.

## §C output — produced by the model

Per [[feature-contract]] §C: `p_delay_{15,60,180}`, `expected_delay_min`, `delay_p10/p90_min`, `cancel_prob`, `reason_codes[]`, `confidence`, and audit fields (`model_version`, `training_window`, `calibration.brier`, `snapshot_id`). `reason_codes[]` = top SHAP/gain attributions from the GBM (transparency wedge — [[differentiation-thesis]]).

## ⛓ Contract gaps — BINDING, flagged to [[staff-product-engineer]]

Grounded in the repo, not the contract's aspiration:

1. **BTS spine has no delay label.** `pipeline/.../staging/stg_bts_on_time.sql` + the `bts_on_time` ingest carry only `flight_date, origin/dest, carrier, cancelled, cancellation_code, diverted, year_month`. There is **no `CRSDepTime/DepTime/DepDelay`, `ArrDelay`, `CRSElapsedTime/ActualElapsedTime`.** ⇒ §A's `hist_on_time_ratio` / `hist_delay_p50/p90` and the T2/T3 **label cannot be BTS-derived today.** The only delay in the repo (`fct_flight_performance.delay_minutes`) is an **OpenSky block-time-vs-route-median proxy** — and OpenSky is **non-commercial** ([[architecture-summary]] dec. 2), so it **cannot be the commercial training label.** → **ML needs the BTS ingest + `stg_bts_on_time` extended to carry the on-time-performance fields** (`CRSDepTime`, `DepDelay`/`ArrDelay`, elapsed times) before T2/T3 can train commercially. **This blocks the delay model.** `#task/eng 🔺 ⛓ [[feature-contract]]`
2. **`dep_hour_bucket` needs a scheduled departure time** — same gap (needs `CRSDepTime` from BTS). Today's spine is date-grain only. `#task/eng 🔺`
3. **No historical weather archive for training the day-of model.** §B lists `signals.metar` as a training source, but the pipeline has no METAR backfill asset yet. Point-in-time historical METAR/TAF is required to train (not just serve) the §B model. Confirm backfill scope + retention. `#task/eng 🔼 ⛓ [[ingestion-backfill]]`
4. **Feature-vector dtypes/encoding** — confirm native-categorical indices vs pre-encoded ints, null sentinels, and `observed_at` staleness flags reach the model. `#task/ml`

Until (1)–(3) resolve, a **defensible v1 = booking-time base-rate + cancellation model on BTS only** (no fresh, no day-of magnitude), which is exactly the MVP scope [[research-summary]] flags as the fallback. State this to [[sales]] — it caps the day-of/paid story.

## Sources

- [[feature-contract]] §A/§B/§C — repo vault, accessed 2026-08-08
- Repo: `pipeline/transforms/models/staging/stg_bts_on_time.sql`, `intermediate/fct_flight_performance.sql`, `assets/bts_on_time.py` — accessed 2026-08-08
- [[architecture-summary]] dec. 2 (OpenSky non-commercial) — accessed 2026-08-08
