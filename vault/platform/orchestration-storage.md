---
type: platform
title: Orchestration & Storage — Dagster, Object Store, Catalog, Metadata DB, Cache
tags: [platform, dagster, iceberg, r2-data-catalog, seaweedfs, r2, postgres, redis, storage]
status: draft
updated: 2026-08-10
---

# Orchestration & Storage

> Where Dagster runs, and what replaces the self-hosted SeaweedFS + Nessie + Postgres + Redis stack (`docker-compose.yml`). Consumes [[ingestion-backfill]], [[iceberg-duckdb]]. Feeds [[hosting-options]], [[cost-model]], [[platform-summary]]. Syncs [[staff-product-engineer]], [[security-engineer]].

## Current self-hosted topology (baseline to beat)

`docker-compose.yml` runs **7 long-lived containers**: `postgres` (Dagster storage), `nessie` (Iceberg REST catalog, JDBC→Postgres), 4× `seaweedfs-*` (master/volume/filer/s3), plus `dagster-webserver` + `dagster-daemon`. Every one is an ops liability for a solo team: patching, volume management, the `-max=64` volume tuning already needed, healthcheck babysitting. The goal is to delete as many of these as possible.

## The consolidation move (headline)

**Cloudflare R2 + R2 Data Catalog collapses `seaweedfs-*` (4 containers) + `nessie` (1 container) into ONE managed, zero-egress, near-free service.** R2 is S3-compatible (drop-in for the existing `httpfs` / boto3 path-style config in `frontend_exports._configure_s3`); R2 Data Catalog is a managed **Iceberg REST catalog** that PyIceberg/DuckDB talk to over the standard REST API. At 2–4 GB slow-growing data ([[ingestion-backfill]] §1.2) both sit inside free tiers → effectively **$0**.

> [!important] DECISION (owned by [[staff-platform-engineer]], 2026-08-10): drop Nessie, adopt R2 Data Catalog, **abandon data-versioning entirely.**
> **Nessie is removed from the stack — no self-hosted-Nessie fallback.** We commit to **R2 Data Catalog** as the single managed Iceberg REST catalog. **We do NOT need git-like data versioning** (Nessie branches/tags): the product is B2C, forward-looking, and has no reproducible-snapshot contract to honour (the B2B feed that motivated snapshot-pinning is dropped — B2C only). Consequences engineering must align to ([[ingestion-backfill]], [[iceberg-duckdb]] — flag to [[staff-product-engineer]]):
> - **Safe re-runnable backfills use overwrite-by-`year_month`** ([[ingestion-backfill]] §1.3 idempotency), **not** a `backfill/*` branch-then-merge ([[ingestion-backfill]] §1.4 is retired). One partition = one atomic table overwrite; readers never see a half-loaded month because each partition write is transactional in Iceberg.
> - **Iceberg still keeps per-table snapshot history** (native to the format, catalog-agnostic) → time-travel + rollback for recovery remain available; what we give up is *named branches*, which we don't use.
> - **Beta risk accepted:** R2 Data Catalog is public beta (billing enabled 2026-08-03). If it proves inadequate before GA, the fallback is **another managed Iceberg REST catalog** (AWS Glue / Apache Polaris-based), **not** re-introducing self-hosted Nessie. The *data* lives in R2 regardless, so a catalog swap is metadata-only. `#task/platform 🔼`

## Component-by-component decision

### 1. Object storage — SeaweedFS → **Cloudflare R2** ✅

| Store | Storage $/GB-mo | Egress | Free tier | Verdict |
|---|---|---|---|---|
| **Cloudflare R2** | **$0.015** | **$0 (zero egress)** | 10 GB + 1M Class-A + 10M Class-B ops/mo | **primary** |
| Backblaze B2 | $0.00695 | free ≤3× stored, then $0.01/GB | 10 GB | cheaper storage, but ~6–12 GB free egress too low for a **public** Parquet dataset |
| Scaleway Object Storage | €0.01606 | 75 GB free, then €0.01/GB | 75 GB egress | EU-region option; metered egress |
| AWS S3 Standard | ~$0.023 | 100 GB free, then **$0.09/GB** | $200 credits (new acct) | egress makes public serving unsafe — reject |

**Why R2:** the frontend serves **public Parquet with unbounded, unpredictable download volume** ([[frontend-backend-split]]). Zero egress means a dataset going viral costs $0 in transfer; S3 would bill $0.09/GB. Same store backs both the anon public `frontend-exports` and the private warehouse — split by bucket + credentials, not by provider. At 2–4 GB storage ≈ **$0.03–0.06/mo**, inside the free tier → **~$0**.

### 2. Iceberg catalog — Nessie → **R2 Data Catalog** (chosen; no fallback catalog) ✅

| Catalog | Model | Cost at our scale | Ops | Verdict |
|---|---|---|---|---|
| **R2 Data Catalog** | managed Iceberg REST, co-located w/ R2 | free tier: 1M catalog ops + 10 GB compaction/mo → **~$0** | **zero** (managed); beta | **chosen** |
| Self-host Nessie | 1 container, JDBC→Postgres | container + DB cost only | low (1 vs 5 containers) | **dropped** — see decision box |
| AWS Glue Catalog | managed | 1M objects + 1M req free, then $1/100k obj | higher-ops, not co-located w/ R2 | emergency-only alt |
| Apache Polaris (self/managed) | Iceberg REST, Snowflake-donated (Apache) | infra/managed cost | medium (young project) | not needed |
| Dremio Arctic (managed Nessie) | **discontinued** → "Open Catalog / Polaris" | n/a | moved target | reject |

#### Why was Nessie the alternative and not Polaris? (answering the PR question)

Nessie appeared as the natural alternative purely because **it is what the repo already runs** (`docker-compose.yml` `nessie:0.104.4`) and what the `travelpal-iceberg-nessie` skill + legacy `tech_product_Architecture.txt` §3.2 built around — the comparison was "keep the incumbent vs replace it," not a greenfield catalog bake-off. The deciding factor Nessie offered was **git-like branching** ([[ingestion-backfill]] §1.4), which we have now **explicitly decided we don't need** (decision box above). **Apache Polaris** (Snowflake-donated, Apache-incubating) is a perfectly valid Iceberg REST catalog, but it wasn't the incumbent, is a younger project, and — critically — it is still **a catalog we'd have to host or buy** (Dremio's managed "Open Catalog" is Polaris-based). It solves the same problem as R2 Data Catalog with **more ops and no co-location** with our R2 storage. So the real choice was never Nessie-vs-Polaris; it was **"any Iceberg REST catalog" vs "the managed one co-located with the object store we already picked."** R2 Data Catalog wins on ops + $0 co-location. **This whole comparison is now largely moot: we commit to R2 Data Catalog; Glue/Polaris survive only as a metadata-only emergency swap if R2's beta disappoints.**

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

## Local testing & dev/prod isolation (answering the PR question)

**Problem:** R2 + R2 Data Catalog are managed Cloudflare services — you **cannot run them on `localhost`**. A product engineer must be able to run the pipeline + tests offline and against a non-prod target without touching prod data. Two separate concerns, two mechanisms:

### A. Local / offline testing (no Cloudflare account needed)

The stack is **S3-API + Iceberg-REST-API on both ends**, so we test against local stand-ins that speak the same protocols — the app code (`_configure_s3`, `httpfs`, PyIceberg REST config) only changes **endpoint + credentials**, never logic:

| Prod service | Local stand-in for tests | Layer ([[travelpal-testing-layers]]) |
|---|---|---|
| R2 (S3 API) | **MinIO** container, or **moto** mock (already used for SeaweedFS per `travelpal-seaweedfs` skill) | unit / integration |
| R2 Data Catalog (Iceberg REST) | **`apache/iceberg-rest-fixture`** (or a **local Polaris**) container in a dev-only compose profile; or **PyIceberg `SqlCatalog`** (SQLite-backed) for pure unit tests | integration |
| Neon Postgres | local `postgres` container (the compose service already exists) | integration |
| Upstash Redis | local `redis` container / `fakeredis` | unit / integration |

- Keep a **`docker-compose.dev.yml` (or a `dev` profile)** with MinIO + an Iceberg-REST-fixture + postgres + redis. This is the **local dev/test rig only** — it is *not* the production topology (we deleted SeaweedFS/Nessie from prod; the local rig is disposable and unversioned-data is fine).
- E2E ([[travelpal-testing-layers]]) runs against this local rig, exactly as the current Playwright + DuckDB-WASM UAT does (`CLAUDE.md`), so the mandated end-to-end test path is preserved without cloud access.

### B. Environment isolation (dev vs prod, both on Cloudflare)

**R2 Data Catalog is enabled per-bucket**, which gives natural isolation — use **two R2 buckets** (ideally in **two Cloudflare accounts**, or at minimum two buckets + two scoped API tokens):

| Env | R2 bucket(s) | Catalog | Compute | Secrets |
|---|---|---|---|---|
| **dev/staging** | `travelpal-dev-warehouse`, `travelpal-dev-exports` | R2 Data Catalog on the dev bucket | Fly `travelpal-dev` app + Neon **dev branch** | separate scoped R2 token, dev Fly secrets |
| **prod** | `travelpal-warehouse`, `travelpal-exports` | R2 Data Catalog on the prod bucket | Fly `travelpal` app + Neon prod | prod-only scoped token |

- **Neon branching** gives a zero-cost throwaway `dev` DB copy for Dagster metadata (Neon's one genuinely useful "versioning" feature — for the *metadata DB*, not the lakehouse).
- **Blast-radius rule:** the dev R2 API token is scoped to dev buckets only, so a dev run **physically cannot** write prod data — isolation by credentials + bucket, same principle as the anon-public vs private split. Coordinate token scoping with [[security-engineer]].
- **Promotion:** code promotes dev→prod via CI/branch merge; **data does not need promotion** (forward daily ingestion re-derives prod tables from source — [[ingestion-backfill]]), which is exactly why dropping data-versioning is safe here.

`#task/platform 🔼 ⛓ [[staff-product-engineer]]` (owns the dev compose rig + test wiring) · `#task/platform 🔺 ⛓ [[security-engineer]]` (token scoping)

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
