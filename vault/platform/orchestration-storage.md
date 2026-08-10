---
type: platform
title: Orchestration & Storage — Dagster, Object Store, Catalog, Metadata DB, Cache
tags: [platform, dagster, iceberg, nessie, seaweedfs, r2, postgres, redis, storage]
status: draft
updated: 2026-08-08
---

# Orchestration & Storage

> Where Dagster runs, and what replaces the self-hosted SeaweedFS + Nessie + Postgres + Redis stack (`docker-compose.yml`). Consumes [[ingestion-backfill]], [[iceberg-duckdb]]. Feeds [[hosting-options]], [[cost-model]], [[platform-summary]]. Syncs [[staff-product-engineer]], [[security-engineer]].

## Current self-hosted topology (baseline to beat)

`docker-compose.yml` runs **7 long-lived containers**: `postgres` (Dagster storage), `nessie` (Iceberg REST catalog, JDBC→Postgres), 4× `seaweedfs-*` (master/volume/filer/s3), plus `dagster-webserver` + `dagster-daemon`. Every one is an ops liability for a solo team: patching, volume management, the `-max=64` volume tuning already needed, healthcheck babysitting. The goal is to delete as many of these as possible.

## The consolidation move (headline)

**Cloudflare R2 + R2 Data Catalog collapses `seaweedfs-*` (4 containers) + `nessie` (1 container) into ONE managed, zero-egress, near-free service.** R2 is S3-compatible (drop-in for the existing `httpfs` / boto3 path-style config in `frontend_exports._configure_s3`); R2 Data Catalog is a managed **Iceberg REST catalog** that PyIceberg/DuckDB talk to exactly like Nessie's REST endpoint. At 2–4 GB slow-growing data ([[ingestion-backfill]] §1.2) both sit inside free tiers → effectively **$0**.

> [!warning] Beta risk
> **R2 Data Catalog is public beta** (billing enabled 2026-08-03). Confirm GA/SLA before a paid launch. Fallback: keep **Nessie self-hosted as one small container against managed Postgres** (Nessie is JDBC-backed, so it rides whatever Postgres we pick) — far lower ops than SeaweedFS, and Iceberg-on-S3 means the *data* already lives in R2 regardless of catalog choice. **Nessie branch-per-backfill workflow ([[ingestion-backfill]] §1.4) is preserved on R2 Data Catalog** (Iceberg-native branching); verify branch semantics parity during migration. `#task/platform 🔼`

## Component-by-component decision

### 1. Object storage — SeaweedFS → **Cloudflare R2** ✅

| Store | Storage $/GB-mo | Egress | Free tier | Verdict |
|---|---|---|---|---|
| **Cloudflare R2** | **$0.015** | **$0 (zero egress)** | 10 GB + 1M Class-A + 10M Class-B ops/mo | **primary** |
| Backblaze B2 | $0.00695 | free ≤3× stored, then $0.01/GB | 10 GB | cheaper storage, but ~6–12 GB free egress too low for a **public** Parquet dataset |
| Scaleway Object Storage | €0.01606 | 75 GB free, then €0.01/GB | 75 GB egress | EU-region option; metered egress |
| AWS S3 Standard | ~$0.023 | 100 GB free, then **$0.09/GB** | $200 credits (new acct) | egress makes public serving unsafe — reject |

**Why R2:** the frontend serves **public Parquet with unbounded, unpredictable download volume** ([[frontend-backend-split]]). Zero egress means a dataset going viral costs $0 in transfer; S3 would bill $0.09/GB. Same store backs both the anon public `frontend-exports` and the private warehouse — split by bucket + credentials, not by provider. At 2–4 GB storage ≈ **$0.03–0.06/mo**, inside the free tier → **~$0**.

### 2. Iceberg catalog — Nessie → **R2 Data Catalog** (primary) / self-host Nessie (fallback) ✅

| Catalog | Model | Cost at our scale | Ops |
|---|---|---|---|
| **R2 Data Catalog** | managed Iceberg REST, co-located w/ R2 | free tier: 1M catalog ops + 10 GB compaction/mo → **~$0** | **zero** (managed); beta |
| Self-host Nessie | 1 container, JDBC→Postgres | container + DB cost only | low (1 container vs 5) |
| AWS Glue Catalog | managed | 1M objects + 1M req free, then $1/100k obj | higher-ops, not co-located w/ R2 |
| Dremio Arctic (managed Nessie) | **discontinued** → "Open Catalog / Polaris" | n/a | reject (moved target) |

### 3. Dagster metadata DB — self-host Postgres → **Neon (free, scale-to-zero)** ✅

Dagster needs Postgres for run/event/schedule storage. Neon **Free** tier: 0.5 GB, scale-to-zero after 5 min idle, no expiry → **$0** for a small metadata DB. Beats Supabase Free (pauses after 1 week inactivity, awkward for a scheduler), Render Postgres free (**expires after 90 days** — reject), and Fly Managed Postgres (from **$38/mo**, no free tier — overkill). If a paid floor is wanted for reliability, Neon **Launch** is pay-as-you-go (~$0.106/CU-hr + $0.35/GB-mo), still cents/mo here.

### 4. Redis hot cache — **Upstash Redis (free → pay-as-you-go)** ✅

Serve-time fresh-signal cache ([[serving-service]]; small, keyed `station+hour`). Upstash **Free**: 256 MB, 500K commands/mo, 10 GB bandwidth → **$0** at MVP. Pay-as-you-go $0.20/100K commands past free. Serverless + scale-to-zero fits the low-ops goal. (Fly has no first-party Redis → points to Upstash anyway; Scaleway Managed Redis from ~€35/mo — reject on cost.)

### 5. Dagster runtime — **self-host container + Neon** (primary) vs **Dagster+ Solo** (runner-up)

| Option | Cost | Ops | Verdict |
|---|---|---|---|
| **Self-host** (webserver+daemon container on the chosen backend host, → Neon Postgres) | host compute + **$0** Postgres | run 1–2 processes; no metered per-materialization cost | **primary** — cheapest, no lock-in, full control |
| **Dagster+ Solo** | **$10/mo + $0.040/credit + $0.010/serverless-min**, no free tier | zero infra; hosted UI/alerting | runner-up — worth ~$10–15/mo only if you value zero-ops orchestration |

For a solo team with a **scheduled monthly-batch + a few polls** workload ([[ingestion-backfill]] §4), self-host wins: credits (1 per materialization/op) accrue real cost under Dagster+ for little gain, and there's **no permanently-free tier** (30-day trial only). Keep Dagster+ Solo as the escape hatch if orchestration ops ever become a burden.

## Net result: 7 containers → ~1

| Was (compose) | Becomes |
|---|---|
| 4× `seaweedfs-*` + `nessie` | **R2 + R2 Data Catalog** (managed, ~$0) |
| `postgres` | **Neon Free** (managed, $0, scale-to-zero) |
| Redis (implied, [[serving-service]]) | **Upstash Free** (managed, $0) |
| `dagster-webserver` + `dagster-daemon` | **1 self-hosted container** on the backend host (see [[hosting-options]]) |

Only Dagster (and the FastAPI service) remain as things we run. Everything stateful is managed and near-free at MVP scale.

## Handoffs

- → [[hosting-options]]: Dagster + FastAPI need a compute host; storage/catalog/DB/cache are now managed line items.
- → [[cost-model]]: all of §1–4 are **~$0 at MVP** (free tiers); Dagster runtime cost folds into the backend host.
- ↔ [[staff-product-engineer]]: R2 is S3-compatible → existing `_configure_s3` / `httpfs` path-style config ports directly; confirm DuckDB `iceberg` extension works against R2 Data Catalog REST endpoint ([[iceberg-duckdb]] open Q). `#task/platform 🔼`
- ↔ [[security-engineer]]: bucket-level split for anon-public `frontend-exports` vs private warehouse; R2 API-token scoping; Neon/Upstash secrets. **No `vault/security/` notes exist yet — assumptions flagged, sync required.** `#task/platform 🔺`

## Sources

- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/) — accessed 2026-08-08 *(measured)*
- [Cloudflare R2 Data Catalog](https://developers.cloudflare.com/r2/data-catalog/) + [pricing](https://developers.cloudflare.com/r2/data-catalog/platform/pricing/) — accessed 2026-08-08 *(measured; public beta)*
- [Backblaze B2 pricing](https://www.backblaze.com/cloud-storage/pricing) · [Scaleway Object Storage](https://www.scaleway.com/en/pricing/storage/) · [AWS S3 pricing](https://aws.amazon.com/s3/pricing/) — accessed 2026-08-08 *(measured; S3 storage rate estimated)*
- [Neon pricing](https://neon.com/pricing) · [Supabase pricing](https://supabase.com/pricing) · [Render pricing](https://render.com/pricing) · [Fly Managed Postgres](https://fly.io/docs/mpg/) — accessed 2026-08-08 *(measured; Fly/Render figures partly secondary)*
- [Upstash Redis pricing](https://upstash.com/pricing/redis) — accessed 2026-08-08 *(measured)*
- [Dagster+ pricing](https://dagster.io/pricing) — accessed 2026-08-08 *(measured; "effective May 1, 2026")*
- [AWS Glue pricing](https://aws.amazon.com/glue/pricing/) · [Dremio pricing](https://www.dremio.com/pricing/) — accessed 2026-08-08 *(measured)*
- Repo: `docker-compose.yml`, `pipeline/pipeline/assets/frontend_exports.py`, `tech_product_Architecture.txt` §3.5 — accessed 2026-08-08
