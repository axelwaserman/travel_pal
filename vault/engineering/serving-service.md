---
type: engineering
title: Serving Service (FastAPI Prediction API)
tags: [engineering, serving, fastapi, api, pydantic, metering, b2c]
status: draft
updated: 2026-08-10
---

# Serving Service — FastAPI Prediction API

> The always-on service that resolves a flight, assembles features, calls the model, and returns a calibrated prediction — with metering. **B2C only.** Consumes [[feature-contract]], [[iceberg-duckdb]], [[frontend-backend-split]]. Feeds [[product-shape-by-tier]], [[security-engineer]], [[staff-platform-engineer]]. See [[architecture-summary]].

Product framing (per PR #13): the app sells **"the best-fitting flight for your buck"** — route-shopping that surfaces the most reliable option for the money — not "transparency." The API exists to answer that decision.

## Why FastAPI (open-stack justification)

Stack is **Python 3.14** / Pydantic v2 (`CLAUDE.md`). FastAPI is the native fit: Pydantic v2 request/response models for free, async (matches `pyreqwest` fresh-signal pulls + async model calls), ASGI for low-latency online serving. Rejects the legacy Go gateway — a second language raises ops cost for no gain at our scale. **Marked: proposed addition, pending Pre-Code Gate.**

## Service structure — functional, small per-module files

Functional composition, **not** one monolith and **not** one shared `models.py`. Each capability is its own module with its **own local `models.py`** (high cohesion, small files per `common/coding-style.md`).

```
serving/
  app.py                 # FastAPI app factory: mounts routers + middleware
  config.py              # Pydantic BaseSettings
  predict/
    router.py            # POST /v1/predict
    service.py           # orchestration: resolve → features → infer (pure-ish)
    models.py            # PredictRequest / PredictResponse / DelayPrediction
  resolve/
    flight.py            # flight_number | route → (carrier, o, d, sched_dep)
    models.py            # ResolvedFlight
  features/
    base_rates.py        # DuckDB read_parquet(feat_route_base_rates)
    fresh_signals.py     # Redis fetch + staleness check
    models.py            # FeatureVector / FreshSignal
  inference/
    engine.py            # load artifact at boot, predict()
    models.py            # ModelMeta
  metering/
    limiter.py           # Redis token-bucket (5 free searches/day, MVP)
    models.py            # Quota
```
- Modules pass **Pydantic models** to each other; each file stays <~200 lines, single responsibility.
- No cross-module `models.py` import chains beyond the DTO each caller needs.

## Request flow (online path)

```
POST /v1/predict
  → validate (predict/models.py)
  → resolve/flight.py: flight_number|route → (carrier, origin, dest, sched_dep)
  → features/base_rates.py: fetch §A row (DuckDB read_parquet, pre-materialized, ~ms)
  → if day-of & within lead window: features/fresh_signals.py from Redis (staleness-checked)
  → assemble FeatureVector (feature-contract §A+§B)
  → inference/engine.py: predict()  (versioned artifact loaded once at boot, in-proc)
  → PredictResponse (feature-contract §C) + freshness + metering headers
```
- **Batch/online split:** Dagster `batch_score` precomputes base-rate predictions for popular routes into Parquet/Redis; the online request returns the base-rate result instantly and, only for day-of, applies the **fresh-signal delta**. Cold/rare routes compute base-rate live.

## Pydantic contract (proposed — lives in `predict/models.py`)

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
    meta: PredictionMeta   # model_version, training_window,
                           # signal_freshness{signal: observed_at|stale},
                           # searches_remaining_today, is_day_of
```
Full field semantics live in [[feature-contract]] §C. Stable versioned contract (`/v1/`) so the app can depend on it.

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

## Rate-limiting / metering (B2C, MVP = limited mode)

- **B2C only** — B2B is dead. **MVP phase 1 = limited mode: 5 free route searches/day.** No paid tiers, no full pricing in phase 1 ([[product-shape-by-tier]]).
- **Metering unit:** one route search / prediction (`POST /v1/predict`). Enforced via **Redis token-bucket keyed on device/session id** (no login in MVP) → soft daily cap of 5, then a friendly upsell wall.
- Descriptive edge reads are **not** metered (they never hit this service — [[frontend-backend-split]]).
- Full pricing/tiers deferred past phase 1.

## Dagster (batch) vs serving (online) responsibility split

| Dagster scheduled jobs | Always-on serving service |
|---|---|
| backfill, spine top-up, `feature_build`, `batch_score`, retraining ([[ingestion-backfill]] §4) | online feature join + inference, metering |
| writes Parquet/Iceberg (R2) + Redis warm cache | reads them; never writes the spine |

## Endpoints (v1)
`POST /v1/predict` · `GET /v1/routes/{o}/{d}/reliability` (base-rate, cache-friendly) · `POST /v1/alerts` (day-of watch — later phase).

## Handoffs
- → [[staff-ml-engineer]]: artifact load interface + `predict()` signature ([[feature-contract]]).
- → [[security-engineer]]: abuse/cost attacks on metered + fresh-pull paths, device-id metering integrity, input validation at the boundary.
- → [[staff-platform-engineer]]: host the always-on ASGI service + Redis; autoscale on qps.

## Open questions
- [ ] Device/session-id metering vs anonymous IP for the 5/day cap — abuse-resistance vs friction. `#task/eng 🔼 ⛓ [[security-engineer]]`
- [ ] Sync vs async model call (in-proc lib vs sidecar) — depends on ML's chosen family. `#task/eng ⛓ [[staff-ml-engineer]]`
- [ ] Alert delivery channel (push/email) + scheduling — later phase. `#task/eng 🔽`

## Sources
- Repo: `CLAUDE.md` (Python 3.14, Pydantic, no-Go), `pipeline/pipeline/assets/frontend_exports.py` (DuckDB S3 read pattern) — accessed 2026-08-10
- `~/.claude` common/patterns.md (API envelope), common/coding-style.md (many small files) — accessed 2026-08-10
