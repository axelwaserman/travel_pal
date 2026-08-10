---
type: ml
title: Training Orchestration — Dagster Assets, Registry, Drift
tags: [ml, dagster, training, registry, nessie, drift]
status: draft
updated: 2026-08-08
---

# Training Orchestration (Dagster)

> How the model is built, versioned, and promoted as Dagster assets over the Iceberg lakehouse. Consumes [[model-selection]], [[features]], `travelpal-dagster-resources` / `travelpal-iceberg-nessie` skills. Feeds [[serving-deployment]], [[evaluation]]. Extends the existing `pipeline/` asset graph.

## Asset graph (extends existing `raw_flights → bts_on_time → transformed_flights → frontend_exports`)

```
bts_on_time (Iceberg spine, extended w/ delay fields — see [[features]] gap #1)
signals.metar (Iceberg weather history — see [[features]] gap #3)
        │
        ▼
training_dataset ─────► point-in-time join (BTS spine + historical METAR), pinned to a Nessie snapshot
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

All resource params use `ResourceParam[X]`; `None`-returning upstreams wired via `AssetIn(dagster_type=Nothing)` (per `travelpal-dagster-resources`). New resource: `model_registry` (SeaweedFS-backed, below). Keep assets small/cohesive (`CLAUDE.md` file rules).

## Data versioning via Nessie (reproducibility)

- `training_dataset` **reads from a pinned Nessie branch/commit** and stamps the `snapshot_id` into the artifact metadata → the `snapshot_id` in [[feature-contract]] §C traces data→model→deployment.
- Train on an **isolated Nessie branch** (`train/<snapshot>`) so a concurrent spine top-up ([[ingestion-backfill]] §1.3) can't move the training data mid-run (`travelpal-iceberg-nessie` branching).
- Lineage chain recorded: `nessie_commit → training_dataset hash → model_version → deployed version`.

## Partitioning & scheduling

| Concern | Design |
|---|---|
| **Retrain cadence** | **Weekly** scheduled job. BTS lags ≤3mo ([[feature-contract]] SLA) → the *base-rate* signal moves slowly; daily retrain is waste. Fresh §B signals are fused at **serve time**, not by retraining. |
| **Backfill / partitions** | Optional monthly `TimeWindowPartition` over BTS `year_month` for reproducible historical training sets; batch_score partitioned by airport prefix (mirrors `frontend_exports` `{ICAO}/` keying). |
| **Drift-triggered retrain** | Dagster **sensor** monitors rolling-window **calibration drift** (Brier/ECE + interval coverage) and feature/PSI drift on live vs training distributions; breach → materialize the training job off-cadence. |

## Model registry — recommend LIGHTWEIGHT, MLflow optional

Per [[AGENTS]] rule 3 ("keep footprint small") and the single-engine ethos ([[architecture-summary]] dec. 4):

- **Recommended v1 registry = Iceberg metadata table `ml.model_registry` + artifacts in SeaweedFS.** Row per version: `model_version, snapshot_id, nessie_commit, training_window, metrics{brier,ece,pinball,coverage}, artifact_key, calibration_key, status{staging|champion|archived}, created_at`. Queryable in DuckDB like every other mart; no new service to host ([[staff-platform-engineer]] wins). Artifact keys: `models/{model_name}/{version}/model.txt` + `calibration.json` (see [[serving-deployment]]).
- **MLflow Tracking = optional add** if experiment sweeps grow (sqlite/postgres backend + SeaweedFS artifact store). Justify before adopting — it's a hosted component with ops cost. Default: skip for v1.
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
