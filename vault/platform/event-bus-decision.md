---
type: platform
title: Event Bus — Needed or Not?
tags: [platform, event-bus, streaming, dagster, redis, architecture-decision]
status: draft
updated: 2026-08-08
---

# Event Bus — Decision

> Do fresh-signal ingestion and near-real-time updates actually need a message bus (Kafka / NATS / Redis Streams / managed SQS / Scaleway pub-sub), or do scheduled Dagster pulls + a Redis cache suffice? Consumes [[ingestion-backfill]], [[serving-service]]. Feeds [[platform-summary]], [[hosting-options]]. Syncs [[staff-product-engineer]].

## Verdict: **NO event bus for MVP (and almost certainly not Phase 1 either).** ✅

A bus is **rejected** as unjustified complexity. The data-flow shape is **poll-and-cache**, not **stream-and-react**. Adding a bus would raise the ops burden (a broker to run, monitor, secure, and pay for) with zero product capability gained at our scale.

## Why the shape doesn't need a bus

The system has exactly two ingestion modes ([[ingestion-backfill]]), neither of which is event-driven:

| Flow | Cadence | Volume | Natural mechanism |
|---|---|---|---|
| BTS historical spine | monthly batch (+ trailing-3 re-materialize) | ~600–650k rows/mo, one file | **Dagster scheduled asset** (already built) |
| METAR/TAF weather | poll hourly (SPECI ad-hoc) | ~small; keyed `station+hour` | **Dagster sensor/schedule → Redis cache** |
| FAA GDP / ground-stop | poll 5–15 min | tiny (advisories) | **Dagster schedule → Redis cache** |
| NOTAM | poll 15–30 min | small | **Dagster schedule → Redis cache** |
| Live prediction request | synchronous, user-driven | 1 req = 1 response | **FastAPI request/response** ([[serving-service]]) |

Every source is a **pull** on a timer against a public HTTP endpoint. There is no high-volume producer emitting events we must buffer, fan out, or replay. The "near-real-time" requirement (day-of alerts, ≥3–6h lead — [[personas]] P1) is satisfied by a **5–15 min poll cadence**, which a Dagster schedule/sensor delivers directly. Sub-minute latency is not a product requirement.

## The three jobs a bus would do — and how we already cover them

1. **Decoupling / backpressure (shock absorber).** The legacy design (`tech_product_Architecture.txt` §3.1, "Redis Ingestion Buffer") framed Redis as an async buffer decoupling inbound network events from the Parquet write engine — a design for a **high-throughput event-ingestion analytics product**. The predictive pivot is **not** that product: we poll a handful of low-volume gov feeds on a timer. There is no inbound event firehose to absorb. **Redis stays — but as a serve-time hot cache ([[serving-service]]), not as an ingestion bus.**
2. **Fan-out to multiple consumers.** We have one consumer per signal (the cache writer) and one reader (the serving service). No multi-subscriber fan-out.
3. **Durable replay / event sourcing.** Historical replay is served by the **Iceberg time-travel snapshots** (Nessie) and the daily METAR roll-up table ([[ingestion-backfill]] §2) — that *is* our durable log, at batch grain, for free. A Kafka-style retained log would duplicate it.

## What would change the verdict (revisit triggers)

Add a bus **only** if one of these becomes a real, signed requirement — not speculatively (YAGNI):

- [ ] **Push alerts at scale** — if day-of alert delivery needs high-fanout, per-user, at-least-once semantics to push/webhook/email for thousands of watched flights, a lightweight queue (see below) becomes justified. Until then, a Dagster-scheduled alert-evaluation job writing to a delivery table is enough. `#task/platform 🔽 ⛓ [[serving-service]]`
- [ ] **A paid live-status feed** ([[ingestion-backfill]] open Q) that *pushes* (webhook/stream) rather than exposes a poll endpoint — then a thin ingress queue to absorb the push is reasonable.
- [ ] **B2B portfolio scoring** ([[serving-service]] `/v1/predict/batch`) growing into a long-running async job pattern where clients submit and poll — a task queue (not a full event bus) fits.

## If a queue is ever needed, start smallest

Do **not** reach for Kafka/Redpanda (heavy self-host) or managed Kafka (costly, over-featured). Escalation ladder, cheapest-first:

1. **A DB table as a queue** (the managed Postgres already present for Dagster) — `SELECT … FOR UPDATE SKIP LOCKED`. Zero new infra.
2. **Redis Streams / lists** — the Redis instance is already in the stack for caching; adds a durable-ish queue with no new service.
3. **A managed serverless queue** — cheap, scale-to-zero (pricing in [[cost-model]] / [[hosting-options]]).
4. Kafka-class systems only at a scale this product is nowhere near.

## Handoffs

- → [[platform-summary]]: event-bus line item = **none**; Redis remains (serve-time cache only). No broker to host, monitor, or pay for.
- ↔ [[staff-product-engineer]]: confirm alert-delivery mechanism ([[serving-service]] open Q) — if it grows to high-fanout push, revisit trigger #1.
- → [[cost-model]]: bus cost = **$0** (not adopted). Redis cache cost is accounted under [[hosting-options]] §Redis.

## Sources

- Repo: `tech_product_Architecture.txt` §3.1 (legacy "Redis Ingestion Buffer" / event model), `docker-compose.yml` (no broker present today) — accessed 2026-08-08
- Vault: [[ingestion-backfill]] (poll cadences, batch-vs-near-real-time rule), [[serving-service]] (Redis hot cache role), [[personas]] (P1 3–6h lead requirement) — accessed 2026-08-08
