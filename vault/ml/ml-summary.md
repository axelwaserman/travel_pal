---
type: ml
title: ML Summary & Handoff — Delay Prediction
tags: [ml, summary, moc, handoff]
status: draft
updated: 2026-08-08
---

# ML Summary & Handoff

> MOC + recommendation for the ML layer. Links [[problem-framing]], [[model-selection]], [[features]], [[training-orchestration]], [[serving-deployment]], [[evaluation]]. Consumes [[feature-contract]], [[serving-service]], [[frontend-backend-split]], [[architecture-summary]], [[research-summary]], [[personas]], [[tier-matrix]], [[metering-unit]], [[unit-economics]].

## Recommendation (one paragraph)

Model delay as **three coupled tasks** ([[problem-framing]]): a calibrated **cancellation classifier**, a **multi-quantile delay-magnitude regressor** (from which threshold exceedance probabilities are read), all in **LightGBM** — CPU-fast, native-categorical, tiny artifact, fits the `<30 ms` in-proc budget — **wrapped in split-conformal calibration** (CQR for the band, isotonic/Venn-Abers for probabilities). **Reject deep/TFT for v1** (tabular data; GBMs match/beat DL; ops cost); revisit only if a paid live feed unlocks delay-propagation signal with a proven backtest lift. Calibration, not raw accuracy, is the bar ([[research-summary]], [[differentiation-thesis]]).

## Regional models (locked design)

Train **two regional models — `model_us` and `model_eu` — same family/recipe, separate artifacts.** Region is a **partition dimension** across the shared layers (Dagster orchestration, dbt+DuckDB transforms, Iceberg/R2 storage, FastAPI serving). `model_us` rides a deep free-BTS backfill; `model_eu` cold-starts on a forward-growing AeroDataBox spine (thin at launch), serving base-rates + deliberately wide bands and sharpening monthly as history accrues — this **reuses the stale-signal degrade-to-cached fallback** ([[serving-deployment]], [[features]]). Everything below (tasks, LightGBM, conformal, batch/day-of split, registry, gate) applies per region. Plain-language explainer: [[model-primer]].

## Serving split ([[serving-deployment]])

Two native-booster artifacts loaded **in-proc** by [[serving-service]]: **`base_model` (§A-only)** → Dagster `batch_score` precomputes base rates for popular routes (Parquet/Redis) feeding the **Free/edge tier at $0** and the instant online base; **`dayof_model` (§A+§B fresh)** → online, day-of, within lead window = **1 metered LP** ([[metering-unit]]). Stale/missing fresh signals → fall back to base + widened conformal band (this *is* the [[unit-economics]] $0.002/LP degrade-to-cached cost guard). Native LightGBM over ONNX — no edge inference needed ([[frontend-backend-split]]). Rollback = repoint the registry champion pointer.

## Training & registry ([[training-orchestration]])

Dagster assets `training_dataset → {train_cancel, train_delay_quantiles} → calibrate_model → evaluate_model(gate) → register_model → batch_score`, over the Iceberg spine, pinned to a **source-Parquet content fingerprint + immutable timestamp partition per run** for reproducible data→model→deployment lineage (no Nessie/data-versioning layer — dropped team-wide). **Weekly** retrain (BTS lags ≤3mo; fresh signals fused at serve time, not by retraining) + a **drift sensor** (Brier/coverage/PSI) for off-cadence retrain. Registry = **lightweight `ml.model_registry` table (Iceberg/DuckDB) + R2 artifacts** (MLflow optional, deferred — keep footprint small); champion status gates what serving loads.

## Evaluation gate ([[evaluation]])

Primary metrics **Brier/ECE** (T1, T2 per threshold) + **interval coverage & pinball** (T3). **Rolling-origin walk-forward** backtest respecting the BTS lag, point-in-time features, segmented by route sample size / lead time / with-without paid feed, plus a signal-masked degradation test. Promotion gate: no Brier/ECE regression, coverage within tolerance, no pinball regression — **absolute thresholds are TODO, set after the first backtest.** No accuracy numbers invented.

## Feature contract — confirmed WITH engineering, gaps flagged ⛓

Accept [[feature-contract]] §A/§B/§C as the interface ([[features]]). **Binding mismatches flagged back to [[staff-product-engineer]]:**

1. 🔺 **BTS spine has no delay label.** Current `stg_bts_on_time` carries only cancelled/diverted/route/carrier/date — no `CRSDepTime/DepDelay/ArrDelay/elapsed`. The repo's only delay (`fct_flight_performance`) is an **OpenSky proxy = non-commercial**, so it cannot be the commercial label. **Extend the BTS ingest before T2/T3 can train.** *Blocks the delay model.*
2. 🔺 **`dep_hour_bucket` needs `CRSDepTime`** — spine is date-grain today.
3. 🔼 **No historical METAR archive** — day-of model can't train without point-in-time weather history.
4. **Confirm** feature-vector dtypes/encoding + native-categorical contract.

**Fallback if 1–3 slip:** a defensible **v1 = booking-time base-rate + cancellation model on BTS only** (no day-of magnitude) — exactly the stale-US-BTS MVP scope [[research-summary]] anticipates.

## Constraints honored

Stale-BTS spine (≤3mo, US-only) drives weekly retrain + serve-time fusion; **OpenSky non-commercial** ⇒ excluded from commercial training/serving, `late_aircraft_risk` gated on a budgeted paid feed and always optional/degradable. No production code (Pre-Code Gate). Proposed stack additions (LightGBM, MAPIE/conformal, sklearn) are minimal and justified.

## Open questions

1. 🔺 **Calibration bar B2B actually requires + can we hit it vs Foresight** — needs first backtest + a design partner ([[research-summary]] OQ2/OQ3, [[feature-contract]] OQ2). Until then, public claims stay qualitative.
2. 🔺 **BTS delay-field ingest + historical METAR backfill** — gates T2/T3 entirely (⛓ [[staff-product-engineer]], [[ingestion-backfill]]).
3. Paid live-status feed budgeted? — decides whether `late_aircraft_risk` (strongest driver) ever enters the model (⛓ [[sales]]).
4. Confirm feature-vector dtypes/encoding + display rule for cancellation vs delay exceedance.

## Files written (this pass)

`vault/ml/`: [[problem-framing]], [[model-selection]], [[features]], [[training-orchestration]], [[serving-deployment]], [[evaluation]], [[ml-summary]], [[model-primer]].

## Handoffs

- ↔ [[staff-product-engineer]]: `predict()` interface + artifact keys ([[serving-deployment]]); **resolve the 4 feature-contract gaps above**.
- → [[marketing]]: honest calibration/transparency framing only — never accuracy superiority ([[evaluation]], [[differentiation-thesis]]).
- ⛓ [[sales]]: base/day-of split = Free/$0 vs metered-LP boundary — confirm vs [[tier-matrix]].

## Sources

- Repo vault: [[feature-contract]], [[serving-service]], [[frontend-backend-split]], [[architecture-summary]], [[research-summary]], [[personas]], [[differentiation-thesis]], [[tier-matrix]], [[metering-unit]], [[unit-economics]] — accessed 2026-08-08
- Codebase: `pipeline/` assets + dbt models, `travelpal-dagster-resources` / `travelpal-iceberg-nessie` skills, `CLAUDE.md` — accessed 2026-08-08
- External: Grinsztajn 2022, Shwartz-Ziv & Armon 2022, Romano et al. 2019 (cited in [[model-selection]]) — public literature, accessed 2026-08-08
