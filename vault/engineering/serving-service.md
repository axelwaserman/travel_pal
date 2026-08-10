---
type: engineering
title: Serving Service (FastAPI Prediction API)
tags: [engineering, serving, fastapi, api, pydantic, metering]
status: draft
updated: 2026-08-08
---

# Serving Service — FastAPI Prediction API

> The always-on service that resolves a flight, assembles features, calls the model, and returns a calibrated prediction — with metering. Consumes [[feature-contract]], [[iceberg-duckdb]], [[frontend-backend-split]]. Feeds [[product-shape-by-tier]], [[security-engineer]], [[staff-platform-engineer]]. See [[architecture-summary]].

## Why FastAPI (open-stack justification)

Stack is Python 3.13 / Pydantic v2 (`CLAUDE.md`). FastAPI is the native fit: Pydantic v2 request/response models for free, async (matches `pyreqwest` fresh-signal pulls + async model calls), ASGI for low-latency online serving. Rejects the legacy Go gateway (`tech_product_Architecture.txt` §3.3) — a second language raises ops cost for no gain at our scale. **Marked: proposed addition, pending Pre-Code Gate.**

## Request flow (online path)

```
POST /v1/predict
  → validate (Pydantic)
  → resolve flight_number|route → (carrier, origin, dest, sched_dep)
  → fetch §A base-rate row  (DuckDB read_parquet on feat_route_base_rates — pre-materialized, ~ms)
  → if day-of & within lead window: fetch §B fresh signals from Redis (with staleness check)
  → assemble feature_vector  (feature-contract §A+§B)
  → model.predict(vector)    (versioned artifact loaded once at boot, in-proc)
  → response (feature-contract §C) + freshness + metering headers
```
- **Batch/online split:** Dagster `batch_score` precomputes base-rate predictions for popular routes into Parquet/Redis; online request returns the base-rate result instantly and, only for day-of, applies the **fresh-signal delta**. Cold/rare routes compute base-rate live from `feat_route_base_rates`.

## Pydantic contract (proposed)

```python
class PredictRequest(BaseModel):        # one of the two resolvers required
    flight_number: str | None = None    # e.g. "DL123"
    origin: str | None = None           # ICAO
    destination: str | None = None      # ICAO
    carrier: str | None = None          # IATA
    scheduled_departure: datetime       # tz-aware; drives booking vs day-of
    model_config = ConfigDict(frozen=True)

class DelayPrediction(BaseModel):
    p_delay_15: float; p_delay_60: float; p_delay_180: float
    expected_delay_min: float
    delay_p10_min: float; delay_p90_min: float
    cancel_prob: float
    reason_codes: list[str]
    confidence: Literal["high", "medium", "low"]

class PredictResponse(BaseModel):       # envelope per common/patterns.md
    success: bool
    data: DelayPrediction | None
    error: str | None = None
    meta: PredictionMeta   # model_version, training_window, snapshot_id,
                           # signal_freshness{signal: observed_at|stale},
                           # quota_remaining, is_day_of
```
Full field semantics live in [[feature-contract]] §C. Response is a stable versioned contract (`/v1/`) so the B2B feed can depend on it.

## Latency budget (target, **estimated**)

| Stage | Budget |
|---|---|
| validate + resolve | < 15 ms |
| base-rate Parquet read (DuckDB, warm) | < 40 ms |
| fresh-signal cache read (Redis) | < 10 ms |
| model inference (in-proc, tree/GBM class) | < 30 ms |
| **p95 total (warm)** | **< 300 ms** |
Booking-time (no fresh signals) target p95 < 120 ms. Achieved by never touching raw Iceberg on the request path ([[iceberg-duckdb]] rule).

## Caching
- **Base-rate predictions**: Redis + in-proc LRU, keyed on §A grain; TTL = until next spine rebuild.
- **Fresh signals**: Redis, TTL = per-signal SLA ([[feature-contract]] §B).
- **Full response**: short TTL (e.g. 60 s) for booking-time; day-of not cached beyond fresh-signal TTL.

## Rate-limiting / metering / gating (the [[sales]] seam)

- **Metering unit (assumed pending [[sales]]):** one `POST /v1/predict` = one billable prediction. Descriptive edge reads are **not** metered (they never hit this service — [[frontend-backend-split]]).
- **Enforcement:** API-key → tier lookup → **Redis token-bucket** rate limiter (per-key qps + monthly quota). 429 + `Retry-After` on breach; `quota_remaining` in `meta`.
- **Gating hooks:** middleware maps tier → allowed endpoints (`/v1/predict`, `/v1/predict/batch`, `/v1/alerts`) and quota. Free tier gets **no** prediction endpoint — only edge Parquet.
- Hooks feed [[unit-economics]]: every metered call has a known marginal cost (fresh-signal pulls + inference).

## Dagster (batch) vs serving (online) responsibility split

| Dagster scheduled jobs | Always-on serving service |
|---|---|
| backfill, spine top-up, `feature_build`, `batch_score`, retraining ([[ingestion-backfill]] §4) | online feature join + inference, metering, alerts |
| writes Parquet/Iceberg + Redis warm cache | reads them; never writes the spine |

## Endpoints (v1)
`POST /v1/predict` · `POST /v1/predict/batch` (B2B) · `GET /v1/routes/{o}/{d}/reliability` (base-rate, cache-friendly) · `POST /v1/alerts` (day-of watch) · `GET /v1/methodology` (backtest/calibration doc — B2B transparency).

## Handoffs
- → [[staff-ml-engineer]]: artifact load interface + `predict()` signature ([[feature-contract]]).
- → [[security-engineer]]: authn/authz on API keys, abuse/cost attacks on metered + fresh-pull paths, multi-tenant isolation (Phase 2 personal data), input validation at the boundary.
- → [[staff-platform-engineer]]: host the always-on ASGI service + Redis; autoscale on qps.
- ⛓ [[sales]]: confirm metering unit + per-tier quotas (assumed above).

## Open questions
- [ ] Confirm metering unit (per-prediction vs per-seat vs per-route-subscription). `#task/eng 🔺 ⛓ [[sales]]`
- [ ] Sync vs async model call (in-proc lib vs sidecar) — depends on ML's chosen family. `#task/eng ⛓ [[staff-ml-engineer]]`
- [ ] Alert delivery channel (push/email/webhook) + who owns scheduling. `#task/eng`

## Sources
- Repo: `CLAUDE.md` (Python/Pydantic/no-Go), `pipeline/pipeline/assets/frontend_exports.py` (DuckDB S3 read pattern), `tech_product_Architecture.txt` §3.3 — accessed 2026-08-08
- `~/.claude` common/patterns.md (API envelope) — accessed 2026-08-08
