---
type: engineering
title: Feature Contract (Product ↔ ML Seam)
tags: [engineering, ml, contract, features, freshness, sla, b2c]
status: draft
updated: 2026-08-10
---

# Feature Contract — the [[staff-ml-engineer]] seam

> The exact features the model consumes, their source, freshness, and SLA — and the exact prediction it must return. This note is the **binding interface** between [[serving-service]] and [[staff-ml-engineer]]. Consumes [[ingestion-backfill]], [[iceberg-duckdb]], [[personas]] (accuracy/lead-time), [[research-summary]] (calibrated output requirement).

## Two prediction contexts (different feature sets, different freshness)

| Context | Trigger ([[personas]]) | Freshness needed | Feature set |
|---|---|---|---|
| **Booking-time base rate** | Choosing a route/carrier weeks out (P1/P2, B2C) | Stale OK (BTS ~3mo lag) | Historical only (§A) |
| **Day-of forecast** | ≥3–6h before departure (P1/P2, B2C) | Fresh (≤ minutes) | Historical (§A) + fresh (§B) |

## §A — Historical features (batch, from `feat_route_base_rates` Parquet)

Grain: `(carrier_iata, origin, dest, dep_hour_bucket, day_of_week, month)`.

| Feature | Type | Source | Freshness | Null policy |
|---|---|---|---|---|
| `hist_on_time_ratio` | float 0–1 | BTS via dbt | batch, ≤3mo | require `n≥30` else fall back to coarser grain |
| `hist_cancel_rate` | float 0–1 | BTS `agg_*_cancellations` | batch | coarsen if sparse |
| `hist_delay_p50_min` / `p90_min` | float | BTS-derived | batch | route→carrier→global fallback |
| `route_n` (sample size) | int | BTS | batch | drives confidence band width |
| `origin_congestion_idx`, `dest_congestion_idx` | float | BTS airport-level agg | batch | 0 if unknown |
| `carrier_reliability_idx` | float | BTS carrier agg | batch | global mean |
| `dep_hour_bucket`, `day_of_week`, `month`, `season` | categorical | request | n/a | required inputs |

**SLA:** rebuilt after each spine top-up ([[ingestion-backfill]] §1.3); staleness bounded by BTS lag. (No snapshot-pinning — data-versioning is dropped, [[iceberg-duckdb]].)

## §B — Fresh features (day-of only, from hot cache)

| Feature | Source | Freshness SLA | Fallback if stale/missing |
|---|---|---|---|
| `origin_metar_{wind,vis,ceiling,precip_flag}` | NOAA METAR | ≤ 90 min | degrade to base-rate-only + widen band |
| `origin_taf_risk`, `dest_taf_risk` at ETD | NOAA TAF | ≤ 6 h | as above |
| `gdp_active`, `ground_stop` (origin/dest) | FAA NAS Status | ≤ 15 min | assume none, flag lower confidence |
| `late_aircraft_risk` | **paid live-status feed** (OpenSky non-commercial ⇒ gated) | ≤ minutes | omit feature until feed budgeted ([[ingestion-backfill]] OQ) |

**Freshness contract:** every fresh feature carries a `observed_at`; if older than its SLA the serving layer marks it `stale` and the model must degrade gracefully (base-rate fallback + wider uncertainty), never silently use stale data.

## §C — Output the model MUST return (per [[research-summary]] handoff)

Calibration > raw accuracy. Contract:

| Field | Meaning |
|---|---|
| `p_delay_15`, `p_delay_60`, `p_delay_180` | calibrated `P(delay ≥ {15,60,180} min)` |
| `expected_delay_min` | point estimate |
| `delay_p10_min`, `delay_p90_min` | uncertainty band |
| `cancel_prob` | `P(cancelled)` |
| `reason_codes[]` | top feature attributions (weather / late-aircraft / congestion / carrier) — shows the traveller *why* a flight is risky, driving the best-fit choice |
| `confidence` | derived from `route_n` + fresh-signal availability |
| `model_version`, `training_window`, `calibration.brier` | model provenance + user trust |

## Boundary with ML (who owns what)

- **Product eng owns:** feature *materialization* (§A Parquet, §B cache), the request→feature-vector assembly, freshness enforcement, the response schema ([[serving-service]]).
- **ML owns:** model family, training from `feat_route_base_rates` + `signals.metar`, **calibration** (reliability/Brier), the artifact interface (load a versioned artifact from **R2**; `predict(feature_vector) → §C`), retraining triggers.
- **Batch vs online:** ML precomputes base-rate predictions (Dagster `batch_score`) for popular routes; the online service only computes the *fresh-signal delta* on top → keeps p95 low ([[serving-service]]).

## Open questions
- [ ] Agree the exact `feature_vector` field list + dtypes with [[staff-ml-engineer]] (this table is the proposal). `#task/eng 🔺 ⛓ [[staff-ml-engineer]]`
- [ ] Calibration bar for user trust (Brier/reliability) — can lakehouse+ML hit it vs incumbents? `#task/ml ⛓ [[staff-ml-engineer]]`
- [ ] Artifact format + versioning convention (R2 key scheme). `#task/ml`

## Sources
- [[research-summary]] handoff (calibrated `P(delay≥Xh)` + bands), [[personas]] (lead-time), [[differentiation-thesis]] (route-shopping edge) — repo vault, accessed 2026-08-10
- Repo: existing marts `agg_route_timeliness`, `agg_*_cancellations`, `fct_flight_performance.sql` — accessed 2026-08-10
