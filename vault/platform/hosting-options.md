---
type: platform
title: Hosting Options — Component-by-Component Comparison
tags: [platform, hosting, comparison, frontend, fastapi, serverless, cold-start]
status: draft
updated: 2026-08-10
---

# Hosting Options

> Per-component candidate comparison for each piece of the system. Consumes [[serving-service]], [[frontend-backend-split]], [[iceberg-duckdb]], [[ingestion-backfill]]. Feeds [[cost-model]], [[platform-summary]]. Storage/catalog/DB/cache decisions live in [[orchestration-storage]]; this note covers **compute** (frontend + backend) and rolls up the managed line items. Event bus = **none** ([[event-bus-decision]]).

Tag key: **measured** = read off the cited pricing page · **estimated** = arithmetic from measured rates · **assumed** = community/secondary, needs verification. Cold-start seconds are all **assumed** (no vendor SLA) — benchmark the real image before committing.

## 1. Frontend — React + DuckDB-WASM SPA + public Parquet

The SPA is tiny static JS/CSS; the **cost axis is Parquet egress** (public dataset, unbounded downloads via DuckDB-WASM byte-range reads — [[frontend-backend-split]]).

| Candidate | Free bandwidth | Paid entry | Egress overage | Egress model | Verdict |
|---|---|---|---|---|---|
| **Cloudflare Pages + R2** | unmetered | $0 (Pages free) | **$0** | **zero-egress** | **primary** |
| Vercel | 100 GB/mo | Pro $20/mo (1 TB incl.) | **$0.15/GB** | metered | reject on egress |
| Netlify | ~15 GB/mo (new credit model) | Personal $9/mo (~50 GB) | ~$0.13/GB | metered credits | reject on egress |

**Decision: Cloudflare Pages (SPA) + Cloudflare R2 (Parquet).** Zero egress means a dataset going viral costs **$0** in transfer; Vercel would bill ~$1,350/mo at 10 TB egress (9,000 GB × $0.15). Two hard caveats:

1. **Pages static-asset cap = 25 MiB/file.** Parquet marts are "tens of MB" ([[ingestion-backfill]]) → any file >25 MiB **must** be served from **R2** (no cap), not Pages static hosting. Architecture: SPA on Pages, Parquet on a public R2 bucket. Also aligns with keeping `frontend-exports` on the same R2 store as the warehouse ([[orchestration-storage]]).
2. **HTTP Range support is not authoritatively documented** for Pages or R2 public buckets (community reports of quirks). DuckDB-WASM depends on `Accept-Ranges: bytes` + `206 Partial Content`. **Pre-commit test (blocking):** `curl -r 0-1023 <r2-asset-url>` must return `206` + `Content-Range`. `#task/platform 🔺`

## 2. Backend — FastAPI prediction service (the cold-start decision)

Workload: ~500 MB–1 GB container (Python 3.14 + GBT artifact in-proc + embedded DuckDB), 1–2 GB RAM, **p95 < 300 ms warm** ([[serving-service]]).

> [!warning] FLAG — Python-version conflict with `CLAUDE.md` (human to resolve)
> The human directed **Python 3.14** for this product. **`CLAUDE.md` currently pins Python 3.13** with an explicit rationale ("Free-threaded 3.13t was tried and dropped — Docker Hub has no 3.13t-slim and the test stack benefited none"). This note now says **3.14** per the direction, but **I have not edited `CLAUDE.md`** — a code/config file with a locked decision is the human's to change. **Action required:** update `CLAUDE.md`'s Tech-Stack line to 3.14 (and confirm a `python:3.14-slim` base image exists on Docker Hub before we build the Fly container). Until `CLAUDE.md` is updated, treat 3.13-vs-3.14 as **unresolved**. Note: user memory already records the 3.14 preference, reinforcing that `CLAUDE.md` is the stale one. `#task/platform 🔺 ⛓ human`

### The core finding: scale-to-zero is NOT worth it here

A cold start of **1–10 s** on the first request after idle **blows the p95 < 300 ms budget** for interactive inference. Every serverless option either (a) has an unacceptable cold start, or (b) needs a paid keep-warm (provisioned concurrency / min-scale=1) that **costs as much as or more than a cheap always-on box**. Since an always-on 1–2 GB instance is only **~$11–25/mo**, pay for always-on.

| Candidate                       | Always-on 1vCPU/2GB                                     | Scale-to-zero         | Cold start (assumed)         | Model fits?     | Lock-in                        | Verdict                        |
| ------------------------------- | ------------------------------------------------------- | --------------------- | ---------------------------- | --------------- | ------------------------------ | ------------------------------ |
| **Fly.io** (shared-cpu-1x, 2GB) | **~$11.11/mo** (measured)                               | yes (auto-stop)       | ~1–3 s                       | yes             | low (OCI+fly.toml)             | **primary**                    |
| **Render** Standard             | **$25/mo** (measured)                                   | no (paid always warm) | none (paid)                  | yes             | low (container)                | **runner-up** (turnkey)        |
| Scaleway Serverless Containers  | ~€29–33/mo w/ min-scale=1 (est.)                        | yes                   | ~5–10 s                      | yes (≤12 GB)    | low; **EU residency**          | EU option                      |
| AWS App Runner                  | ~$10 idle floor + active vCPU (est.)                    | no (min 1)            | fast wake                    | yes             | med-high                       | AWS-native middle ground       |
| AWS Fargate (arm)               | ~$29/mo (est.)                                          | no                    | n/a                          | yes             | medium                         | pricier, more ops              |
| AWS Lambda (container)          | free-tier + cold starts, or ~$22/mo+ provisioned (est.) | yes                   | ~2–3.5 s (worse for 1 GB ML) | yes (10 GB img) | **high** (Mangum, API GW, IAM) | reject — trap for ML inference |

**Decision: Fly.io always-on `shared-cpu-1x` + 2 GB (~$11.11/mo).** Cheapest always-on, portable container (no lock-in), and it *also* hosts the Dagster runtime ([[orchestration-storage]]) so compute consolidates on one platform. Render Standard ($25/mo) is the runner-up: ~2× the price buys the most turnkey, zero-config, zero-cold-start experience — pick it if orchestration/DevOps time is scarcer than $14/mo. **Never** use Render's Free tier for prod (30–60 s spin-up) or raw serverless scale-to-zero for the inference path.

- **DuckDB memory note:** DuckDB is embedded/in-process ([[iceberg-duckdb]] context B) — it reads narrow pre-materialized Parquet, not raw Iceberg, so 2 GB RAM is ample; size up (Fly 4 GB ~$21/mo) only if batch-adjacent reads grow. Single-node/in-process → watch concurrency; scale by adding instances behind Fly's proxy, not by threading.

## 3. Managed data services (detail in [[orchestration-storage]])

| Component | Choice | MVP cost | Why |
|---|---|---|---|
| Object storage | **Cloudflare R2** | ~$0 (10 GB free) | zero egress; S3-compatible drop-in |
| Iceberg catalog | **R2 Data Catalog** (Nessie dropped; no data-versioning — [[orchestration-storage]]) | ~$0 (free tier) | managed REST catalog, co-located; **beta**; emergency alt = Glue/Polaris, not Nessie |
| Dagster metadata DB | **Neon Free** (scale-to-zero) | $0 | 0.5 GB, no expiry |
| Redis hot cache | **Upstash Free** | $0 | 256 MB, 500K cmd/mo, serverless |
| Orchestration runtime | **self-host Dagster on Fly** (runner-up: Dagster+ Solo $10/mo) | folds into Fly compute | cheapest, no per-materialization credits |

## Roll-up: what we actually operate

**2 platforms we run on (Cloudflare + Fly.io) + 2 managed serverless add-ons (Neon + Upstash).** Down from the 7-container self-hosted compose stack. Only Dagster + FastAPI are processes we manage; everything stateful is managed and free-tier at MVP.

## Handoffs

- → [[cost-model]]: plug these rates into near-zero + moderate scenarios.
- → [[platform-summary]]: primary combo = Fly + Cloudflare + Neon + Upstash.
- ↔ [[staff-product-engineer]]: FastAPI + Dagster co-located on Fly; DuckDB embedded in API reads R2 Parquet.
- ↔ [[security-engineer]]: Fly private networking for API↔Dagster↔Neon↔Upstash; R2 token scoping; TLS. **`vault/security/` not yet written — flagged.** `#task/platform 🔺`

## Sources

- Frontend: [Cloudflare Pages pricing/limits](https://developers.cloudflare.com/pages/functions/pricing/) + [limits](https://developers.cloudflare.com/pages/platform/limits/index.md) · [Vercel pricing](https://vercel.com/pricing) · [Netlify pricing](https://www.netlify.com/pricing/) — accessed 2026-08-08 *(measured; some Netlify credit conversions derived)*
- Backend: [Scaleway Serverless pricing](https://www.scaleway.com/en/pricing/serverless/) + [container limits](https://github.com/scaleway/docs-content/blob/main/pages/serverless-containers/reference-content/containers-limitations.mdx) · [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/) · [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/) · [AWS App Runner pricing](https://aws.amazon.com/apprunner/pricing/) · [Fly.io pricing](https://fly.io/docs/about/pricing/) + [autostop](https://fly.io/docs/launch/autostop-autostart/) · [Render pricing](https://render.com/pricing) — accessed 2026-08-08 *(rates measured; cold-start seconds assumed/community)*
- Managed services: see [[orchestration-storage]] Sources.
- Repo: `docker-compose.yml`, `CLAUDE.md`, `tech_product_Architecture.txt` — accessed 2026-08-08
