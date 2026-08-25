---
type: ml
title: Serving & Deployment — Artifact, Load Contract, Batch vs Online
tags: [ml, serving, deployment, artifact, batch, online, rollback]
status: draft
updated: 2026-08-11
---

# Serving & Deployment

> How the trained artifact reaches [[serving-service]] and how batch vs online scoring splits. Consumes [[model-selection]], [[training-orchestration]], [[feature-contract]], [[serving-service]], [[frontend-backend-split]], [[metering-unit]]. Feeds [[staff-product-engineer]], [[staff-platform-engineer]].

## Artifact format — native booster, in-proc (NOT ONNX for v1)

- **Format:** LightGBM native booster (`model.txt`) + `calibration.json` (conformal residual quantiles + isotonic/Venn-Abers maps) + `feature_spec.json` (ordered feature names, categorical indices, null sentinels, training means for imputation).
- **Why native over ONNX:** the serving path is **in-process Python** ([[serving-service]] "loaded once at boot, in-proc") with a `<30 ms` inference budget a CPU tree meets easily. ONNX buys portable/edge inference we **don't need** — the edge tier is pure descriptive Parquet, never model inference ([[frontend-backend-split]]). Keep footprint small ([[AGENTS]] rule 3). **ONNX revisited only** if inference ever moves to a non-Python host.
- **Load from** R2 `models/{region}/{model_name}/{version}/` (keys from [[training-orchestration]] registry).

## Load contract with [[serving-service]]

```
predict(feature_vector: dict) -> DelayPrediction   # feature-contract §C
```
- Model + calibration + feature_spec loaded **once at boot**; version resolved from `ml.model_registry` champion pointer or a pinned `MODEL_VERSION` env.
- Model object validates the incoming vector against `feature_spec` (fail-fast on schema drift — `AGENTS.md` input-validation).
- Returns §C fields incl. `model_version`, `snapshot_id`, `calibration.brier` for the response `meta`.
- **Sync, in-proc** answers the [[serving-service]] OQ "sync vs async model call": a CPU GBM needs no sidecar. (Async only if a future deep model forces a GPU sidecar.)

## Two artifacts, one split (base vs day-of) — resolves the "fresh-signal delta"

[[feature-contract]] + [[serving-service]] describe an online *fresh-signal delta* on a precomputed base. Cleanest realization:

| Artifact | Trained on | Serves | Metered? |
|---|---|---|---|
| **`base_model`** (§A only) | historical BTS base rates | **batch_score** precompute for popular routes → Parquet/Redis; booking-time online; **Free/edge base rate** | No (Class A — [[metering-unit]]) |
| **`dayof_model`** (§A + §B) | BTS + historical METAR | online, day-of, within lead window, when fresh signals present | **Yes = 1 LP** ([[metering-unit]]) |

- Both share the label, threshold conventions, and conformal method so their outputs are comparable.
- **Online request:** return the cached `base_model` result instantly; **if day-of & fresh signals available**, run `dayof_model` and return its (calibrated) prediction as the fresh delta. If signals stale/missing → fall back to `base_model` + widened band ([[features]] degradation path). This keeps p95 low ([[serving-service]] budget) and maps exactly to the LP metering boundary.
- **Cost guard:** honor [[unit-economics]] "$0.002/LP ceiling → degrade to cached base-rate" — the fallback above *is* that control.

## Batch scoring (the free-tier engine)

`batch_score` Dagster asset ([[training-orchestration]]) precomputes `base_model` §C outputs across the popular `(carrier,origin,dest,hour,dow,month)` grid → Parquet + Redis warm cache. Feeds:
- `GET /v1/routes/{o}/{d}/reliability` (cache-friendly base rate).
- The edge/Free tier's "typically 78% on-time" number ([[frontend-backend-split]]) — **precomputed, $0 online**.
Rebuilt after each spine top-up + retrain; keyed like `frontend_exports` (`{ICAO}/` prefix).

## Versioning, warm-load, rollback

- **Versioning:** `model_version = {name}-{snapshot_id}-{trained_at}`; immutable keys; registry `status` picks champion.
- **Warm-load / deploy:** new champion published to registry → serving instances lazy-reload on next boot or a `/admin/reload` signal; **blue/green** by pinning `MODEL_VERSION` on a canary fleet first.
- **Rollback:** repoint champion (or `MODEL_VERSION`) to the prior version — artifacts are immutable and retained, so rollback is instant and lossless. Gate every promotion through [[evaluation]] before it can become champion.

## Handoff

- → [[staff-product-engineer]]: `predict()` signature, artifact/calibration/feature-spec key scheme, champion-pointer resolution, two-model base/day-of split — confirm this matches [[serving-service]]'s request flow.
- → [[staff-platform-engineer]]: artifacts in R2 (no model server to host); serving loads in-proc; base-rate predictions from an in-process Arrow/DuckDB table over R2 Parquet, small Redis only for rate-limit counters + day-of fresh-signal TTL ([[training-orchestration]]).
- ⛓ [[sales]]: the base/day-of split *is* the Free (Class A, $0) vs LP (metered) boundary — confirm against [[tier-matrix]].

## Sources

- [[serving-service]] (in-proc load, latency budget, batch/online split), [[feature-contract]] §C, [[frontend-backend-split]] (edge = no inference), [[metering-unit]] / [[unit-economics]] (LP boundary, $0.002 ceiling) — repo vault, accessed 2026-08-08
- Repo: `pipeline/pipeline/assets/frontend_exports.py` (SeaweedFS upload + airport-prefix keying) — accessed 2026-08-08
