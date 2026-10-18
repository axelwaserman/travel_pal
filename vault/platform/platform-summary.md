---
type: platform
title: Platform Summary — Primary Recommendation & Handoff
tags: [platform, summary, moc, recommendation, handoff]
status: draft
updated: 2026-08-11
---

# Platform Summary

> One-page hosting recommendation for the whole system, synthesizing [[hosting-options]], [[cost-model]], [[orchestration-storage]], [[event-bus-decision]]. MOC for the `vault/platform/` notes. Consumes [[serving-service]], [[frontend-backend-split]], [[iceberg-duckdb]], [[ingestion-backfill]], [[unit-economics]]. Handoffs to [[staff-product-engineer]], [[security-engineer]], [[sales]].

## Recommendation in three sentences

Run the system on **two platforms — Cloudflare (frontend + object storage + Iceberg catalog) and Fly.io (FastAPI + Dagster) — plus two managed serverless add-ons, Neon (Postgres) and Upstash (Redis)**, collapsing today's 7-container self-hosted compose stack down to two things we actually operate. **Never scale-to-zero the inference path** — a cold start blows the p95 < 300 ms budget, and a cheap always-on Fly box (~$11/mo) is cheaper than any keep-warm. **No event bus** — the data flow is poll-and-cache, and Dagster schedules + Redis already cover it.

## Primary recommendation

| Component                  | Host                                                   | Why (low-ops first, cost second, scale third)                                                                         |
| -------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| **Frontend SPA**           | **Cloudflare Pages**                                   | free, static; low lock-in                                                                                             |
| **Public Parquet**         | **Cloudflare R2**                                      | **zero egress** — a viral free dataset costs $0 to serve; no 25 MiB static cap                                        |
| **FastAPI prediction API** | **Fly.io** always-on shared-cpu-1x/2 GB                | ~$11/mo, meets p95, portable OCI, no lock-in                                                                          |
| **DuckDB compute**         | embedded in FastAPI (serving) + Dagster worker (batch) | single-engine per `AGENTS.md`; reads pre-materialized Parquet, never raw Iceberg on request path ([[iceberg-duckdb]]) |
| **Dagster ETL**            | **self-host on Fly** + Neon Postgres                   | cheapest; no per-materialization credits; escape hatch = Dagster+ Solo $10/mo                                         |
| **Object store + catalog** | **R2 + R2 Data Catalog**                               | one managed service replaces SeaweedFS (4 containers) + Nessie; ~$0 at scale (**beta — verify GA**)                   |
| **Metadata DB**            | **Neon Free** (scale-to-zero)                          | $0; no expiry                                                                                                         |
| **Hot cache**              | **Upstash Redis Free**                                 | $0; serverless                                                                                                        |
| **Event bus**              | **none**                                               | [[event-bus-decision]]                                                                                                |

**Comparison — primary vs runner-up:**

| Axis | Primary (Fly + Cloudflare + Neon + Upstash) | Runner-up (Render + Cloudflare + Neon + Upstash) |
|---|---|---|
| Ops burden | Low — 2 processes on Fly; rest managed | **Lowest** — Render is the most turnkey PaaS |
| Cost @ near-zero | **~$17/mo** | ~$32/mo (Render Standard $25 + Dagster worker) |
| Cost @ moderate | **~$40–50/mo** | ~$55–70/mo |
| Scale-to-zero | Yes (Fly auto-stop) — but **not used** for inference | No on paid tiers |
| Lock-in | Low (portable containers) | Low (portable containers) |
| Region/latency | Global edge (CF) + Fly regions | Global edge (CF) + Render regions (fewer) |
| Egress | **$0** (R2) | **$0** (R2) |

**Runner-up rationale:** swap Fly→Render if the team wants zero DevOps and will pay ~$14–20/mo more for the most hands-off experience (no fly.toml, no machine sizing, guaranteed no cold starts on paid). Both keep the Cloudflare + Neon + Upstash spine identical.

**Rejected:** Vercel/Netlify for Parquet (metered egress → unbounded bills); AWS Lambda for inference (cold-start trap + high lock-in); AWS Fargate/App Runner (pricier, more ops, AWS lock-in); self-host SeaweedFS/Nessie (7 containers of solo-team ops — and Nessie's data-versioning is not needed, [[orchestration-storage]]); ClickHouse as Dagster backend (legacy `tech_product_Architecture.txt` §3.6 — **overkill**; Postgres/Neon is the low-ops fit, and the repo's `docker-compose.yml` already uses Postgres, so ClickHouse was never actually adopted).

## Cost headline

**Fixed infra ≈ $17/mo (MVP) → ~$40–50/mo (moderate).** Dominated by Fly always-on compute; storage + egress ≈ $0 via R2 zero-egress. **~5–15 Plus subs ($39/yr) cover all fixed infra** (product is now **B2C only** — no B2B contract path) — closes the fixed-infra unknown [[unit-economics]] flagged. Platform per-LP marginal ≈ $0, so it does **not** threaten the **$0.002/LP ceiling** (that's weather-API COGS, tracked in [[unit-economics]]). Math: [[cost-model]].

## Event-bus verdict

**NO.** Poll-and-cache, not stream-and-react: Dagster schedules/sensors pull low-volume gov feeds on a timer into Upstash Redis; Iceberg snapshots are the durable replay log. Adding a broker = pure ops cost, no capability. Revisit only for high-fanout push alerts or a push-based paid feed — and even then start with a Postgres/Redis queue, never Kafka. Full reasoning: [[event-bus-decision]].

## Roadmap-blocker flags

1. **R2 Data Catalog is public beta** — the ~$0 managed-catalog win depends on it. **DECISION (2026-08-11): Nessie is dropped and data-versioning abandoned** ([[orchestration-storage]]); we commit to R2 Data Catalog. If its beta disappoints before GA, the fallback is **another managed Iceberg REST catalog (Glue / Polaris), metadata-only swap — NOT re-introducing self-hosted Nessie**. Confirm GA/SLA before paid launch. `#task/platform 🔼`
2. **HTTP Range support unverified** on Cloudflare Pages/R2 — DuckDB-WASM byte-range reads depend on it. **Blocking pre-commit `curl -r` test.** `#task/platform 🔺`
3. **A paid live-status feed** ([[ingestion-backfill]] open Q, [[unit-economics]] risk 3) would add COGS not in this model and could justify revisiting the event-bus verdict — gated on [[sales]] budget.
4. **`vault/security/` does not exist yet** — network-isolation/secrets/presigned-URL requirements are **assumed**, not validated. **Sync required** before provisioning. `#task/platform 🔺 ⛓ [[security-engineer]]`

## Handoffs

- ↔ **[[staff-product-engineer]]**: hosting split confirmed — FastAPI + Dagster on Fly, DuckDB embedded (serving) + worker (batch), R2 S3-compatible so `frontend_exports._configure_s3` / `httpfs` port directly. **Need back:** confirm DuckDB `iceberg` extension works against R2 Data Catalog's REST endpoint ([[iceberg-duckdb]] open Q).
- ↔ **[[security-engineer]]**: **assumptions to validate** — Fly private networking for API↔Dagster↔Neon↔Upstash; R2 API-token scoping (anon-read `frontend-exports` bucket vs private warehouse bucket); secrets in Fly secrets / platform vaults not env files; TLS everywhere; presigned URLs only when Phase 2 personal data lands. **No security notes exist — I assumed a standard posture; please write `vault/security/` and flag conflicts.**
- → **[[sales]]**: fixed infra now sized (**~$17–50/mo**) → break-even ~5–15 Plus subs; feeds [[unit-economics]] break-even. A paid data feed remains the one thing that could move the LP cost floor.

## Files written (this pass)

`vault/platform/`: [[hosting-options]], [[cost-model]], [[orchestration-storage]], [[event-bus-decision]], [[platform-summary]].

## Sources

All pricing cited in [[hosting-options]], [[orchestration-storage]], [[cost-model]] (accessed 2026-08-08; marked measured/estimated/assumed). Cross-refs: [[serving-service]], [[frontend-backend-split]], [[iceberg-duckdb]], [[ingestion-backfill]], [[unit-economics]], [[pricing-summary]]. Repo: `docker-compose.yml`, `AGENTS.md`, `tech_product_Architecture.txt` — accessed 2026-08-08.
