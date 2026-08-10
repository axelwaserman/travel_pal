---
type: ml
title: Training Orchestration — Dagster Assets, Registry, Drift
tags: [ml, dagster, training, registry, drift]
status: draft
updated: 2026-08-10
---

# Training Orchestration (Dagster)

> How the model is built, versioned, and promoted as Dagster assets over the Iceberg lakehouse. Consumes [[model-selection]], [[features]], `travelpal-dagster-resources` / `travelpal-iceberg-nessie` skills. Feeds [[serving-deployment]], [[evaluation]]. Extends the existing `pipeline/` asset graph.

## Asset graph (extends existing `raw_flights → bts_on_time → transformed_flights → frontend_exports`)

```
bts_on_time (Iceberg spine, extended w/ delay fields — see [[features]] gap #1)
signals.metar (Iceberg weather history — see [[features]] gap #3)
        │
        ▼
training_dataset ─────► point-in-time join (BTS spine + historical METAR), pinned to a source-Parquet content fingerprint + immutable timestamp partition
        │
        ├──► train_cancel_model      (LightGBM binary, T1)
        ├──► train_delay_quantiles   (LightGBM quantile heads, T2/T3)
        │
        ▼
calibrate_model ──────► split-conformal (CQR) + isotonic/Venn-Abers on a held-out calibration window
        │
        ▼
evaluate_model ───────► backtest metrics + PROMOTION GATE ([[evaluation]])
        │  (gate pass)
        ▼
register_model ───────► write artifact + metadata to registry (below)
        │
        ▼
batch_score ──────────► precompute §A base-rate predictions for popular routes → Parquet/Redis (feeds Free/edge + online base)
```

All resource params use `ResourceParam[X]`; `None`-returning upstreams wired via `AssetIn(dagster_type=Nothing)` (per `travelpal-dagster-resources`). New resource: `model_registry` (object-store-backed, below). Keep assets small/cohesive (`CLAUDE.md` file rules).

## Could an Arrow-backed store replace Redis for batch_score? (review 2026-08-10)

**What Redis was doing here:** a **hot key-value cache** for precomputed base-rate predictions — the online FastAPI path does a point lookup by `(region, carrier, origin, dest, hour, dow, month)` and needs sub-ms reads, plus TTL eviction and (in [[serving-service]]) the token-bucket rate limiter. Redis is a *serving-latency* component, not analytics.

**Arrow options, honestly weighed:**

| Option | Fit | Verdict |
|---|---|---|
| **Arrow IPC / Parquet on R2 + DuckDB point-read** | batch_score already emits columnar Parquet; the online service can memory-map / `read_parquet` a per-region base-rate table | ✅ **Good for the base-rate lookup** — an in-process Arrow table (or DuckDB over the Parquet) gives µs reads with **zero extra infra**. Attractive now that MVP is limited-mode (5 free searches/day → modest QPS). |
| **Arrow Flight (RPC server)** | a networked columnar service | ❌ Overkill — it's a *bulk* transport for big result sets, not a point-KV cache; adds a server to host for no latency win at our scale. |
| **Redis** | KV + TTL + rate-limit counters in one | ⚠️ Still the simplest home for **rate-limit counters + fresh-signal TTL cache**, which Arrow does not address. |

**Recommendation:** for **base-rate predictions**, prefer an **in-process Arrow/DuckDB table loaded from R2 Parquet** — drops Redis from the *batch_score serve path*, consistent with the team's simplification pass (and DuckDB-WASM now only nice-to-have). **Keep a small Redis (or equivalent) only for rate-limit counters + the day-of fresh-signal TTL cache** — those are genuinely KV/TTL-shaped and not what Arrow is for. Net: Arrow **replaces Redis for the prediction cache, not for metering**. Confirm with [[serving-service]] / [[staff-platform-engineer]]. `#task/ml`

## Reproducibility WITHOUT Nessie (updated 2026-08-10 — platform dropped Nessie→R2 Data Catalog, no data versioning)

Team decision: **no data-versioning layer.** So the earlier Nessie-branch snapshotting is **dropped.** Lighter reproducibility that still traces data→model→deployment:

- `training_dataset` stamps a **content/window fingerprint** into artifact metadata: `(region, min/max flight_date, row_count, ingest_watermark, sha over the source Parquet keys)` — this replaces `snapshot_id`. Cheap, no catalog needed.
- **Isolation instead of branching:** trainings read an **immutable, timestamp-partitioned Parquet snapshot** of the spine (R2 keys are write-once per `year_month`), so a concurrent forward-ingestion top-up can't move training data mid-run. The idempotent overwrite-by-`year_month` pattern ([[ingestion-backfill]]) is what makes a read stable.
- Lineage recorded as: `source-parquet fingerprint → training_dataset hash → model_version → deployed version`. Enough for audit/rollback without a versioned catalog.

## Partitioning & scheduling

| Concern | Design |
|---|---|
| **Retrain cadence** | **Weekly** scheduled job. BTS lags ≤3mo ([[feature-contract]] SLA) → the *base-rate* signal moves slowly; daily retrain is waste. Fresh §B signals are fused at **serve time**, not by retraining. |
| **Backfill / partitions** | Optional monthly `TimeWindowPartition` over BTS `year_month` for reproducible historical training sets; batch_score partitioned by airport prefix (mirrors `frontend_exports` `{ICAO}/` keying). |
| **Drift-triggered retrain** | Dagster **sensor** monitors rolling-window **calibration drift** (Brier/ECE + interval coverage) and feature/PSI drift on live vs training distributions; breach → materialize the training job off-cadence. |

## Model registry — recommend LIGHTWEIGHT, MLflow optional

Per [[AGENTS]] rule 3 ("keep footprint small") and the single-engine ethos ([[architecture-summary]] dec. 4):

- **Recommended v1 registry = a metadata table `ml.model_registry` (Iceberg/DuckDB) + artifacts in R2.** Row per version: `model_version, region, data_fingerprint, training_window, metrics{brier,ece,pinball,coverage}, artifact_key, calibration_key, status{staging|champion|archived}, created_at` (note: `data_fingerprint` replaces the dropped `nessie_commit`/`snapshot_id`; `region` distinguishes `model_us`/`model_eu`). Queryable in DuckDB like every other mart; no new service to host ([[staff-platform-engineer]] wins). Artifact keys: `models/{region}/{model_name}/{version}/model.txt` + `calibration.json` (see [[serving-deployment]]).
- **MLflow Tracking = optional add** if experiment sweeps grow (sqlite/postgres backend + R2 artifact store). Justify before adopting — it's a hosted component with ops cost. Default: skip for v1.
- Registry is the **only** promoter of `status=champion`; the serving service loads whichever version is champion (or a pinned version) — see [[serving-deployment]] rollback.

## Experiment tracking

v1: log metrics + params as rows in `ml.model_registry` (+ artifacts) — auditable in DuckDB. Upgrade to MLflow only when hyperparameter search justifies it.

## Handoff

- → [[serving-deployment]]: artifact + calibration key scheme, champion pointer.
- → [[evaluation]]: `evaluate_model` implements the gate; sensor consumes its drift metrics.
- ⛓ [[staff-product-engineer]] / [[ingestion-backfill]]: `training_dataset` cannot be built until BTS delay fields + historical METAR land ([[features]] gaps 1 & 3). `#task/ml 🔺`

## Sources

- `travelpal-dagster-resources`, `travelpal-iceberg-nessie` skills; repo `pipeline/pipeline/__init__.py`, `assets/frontend_exports.py` (airport-prefix keying, S3 read pattern) — accessed 2026-08-08
- [[ingestion-backfill]] §1.3 (spine top-up idempotency), [[feature-contract]] SLA — repo vault, accessed 2026-08-08
