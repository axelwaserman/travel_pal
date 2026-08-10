---
type: platform
title: Cost Model — Near-Zero + Moderate Usage
tags: [platform, cost, tco, unit-economics, budget]
status: draft
updated: 2026-08-08
---

# Cost Model

> Monthly infra cost of the recommended stack ([[hosting-options]], [[orchestration-storage]]) at (a) near-zero usage and (b) a defined moderate-usage point, with the math shown. Answers the **fixed-infra unknown** [[unit-economics]] flagged. Feeds [[platform-summary]]. Consumes [[serving-service]] (LP definition), [[ingestion-backfill]] (data volumes).

Every figure marked **measured** (off a cited pricing page — see [[hosting-options]]/[[orchestration-storage]] Sources), **estimated** (arithmetic here), or **assumed** (community/secondary). No invented numbers.

## Recommended stack (priced)

Fly.io (FastAPI + Dagster) · Cloudflare (Pages + R2 + R2 Data Catalog) · Neon (Postgres) · Upstash (Redis). Event bus = **none** ([[event-bus-decision]]).

## (a) Near-zero usage — MVP / pre-launch

Assumptions: 2–4 GB Iceberg/Parquet ([[ingestion-backfill]] §1.2); <10 GB/mo edge egress; a few hundred predictions/mo; Dagster runs a monthly BTS batch + a handful of daily polls.

| Line item | Config | $/mo | Basis |
|---|---|---|---|
| FastAPI (always-on) | Fly shared-cpu-1x + 2 GB | **$11.11** | measured (Fly pricing) |
| Dagster daemon (always-on) | Fly shared-cpu-1x + 1 GB | **$5.92** | measured |
| Dagster webserver | Fly, auto-stop (rarely hit) | **~$0–2** | estimated (auto-stop billed only while awake) |
| Object storage | R2, 2–4 GB | **~$0** | measured (10 GB free tier) |
| Iceberg catalog | R2 Data Catalog | **~$0** | measured (1M ops free; **beta**) |
| Postgres | Neon Free (scale-to-zero) | **$0** | measured |
| Redis | Upstash Free | **$0** | measured |
| Frontend static | Cloudflare Pages Free | **$0** | measured |
| Edge egress | R2 zero-egress | **$0** | measured |
| Event bus | none | **$0** | [[event-bus-decision]] |
| **Total** | | **≈ $17–19/mo** | **estimated** (sum) |

**Near-zero headline: ~$17–19/mo, fully dominated by Fly always-on compute.** Everything stateful is $0 on free tiers. Could shave to **~$11/mo** by co-locating the Dagster daemon on the same Fly machine as FastAPI (share one 2 GB instance) — acceptable at MVP; split them before load matters.

## (b) Moderate usage — post-launch traction

Assumptions (all **estimated** usage points):
- **50,000 Live Predictions/mo** ([[serving-service]] metering unit).
- **~2 TB/mo edge Parquet egress** (popular free descriptive tier).
- Storage grown to ~15 GB; ~20M R2 Class-B (read) ops/mo from byte-range reads.
- Redis ~1M commands/mo; Neon light but past free CU-hours.

| Line item | Config | $/mo | Basis |
|---|---|---|---|
| FastAPI | Fly shared-cpu-2x + 4 GB (headroom) | **~$25** | estimated (measured Fly RAM/CPU rates) |
| Dagster (daemon + web) | Fly, 1–2 GB | **~$8–12** | estimated |
| Object storage | R2, 15 GB × $0.015 | **~$0.23** | measured rate |
| R2 read ops | (20M − 10M free) × $0.36/M | **~$3.60** | estimated (measured rate) |
| **Edge egress (2 TB)** | R2 zero-egress | **$0** | **measured — the decisive win** |
| Iceberg catalog | R2 Data Catalog, within/near free | **~$0–2** | estimated |
| Postgres | Neon Launch, pay-as-you-go | **~$2–5** | estimated (measured rates) |
| Redis | Upstash, ~1M cmd (500K free + 500K × $0.20/100K) | **~$1** | estimated (measured rate) |
| Frontend static | Cloudflare Pages | **$0** | measured |
| **Total (platform)** | | **≈ $40–50/mo** | **estimated** |

> The same 2 TB egress on Vercel/Netlify would add **~$150–260/mo** (metered ~$0.13–0.15/GB over the included allowance — [[hosting-options]]). R2 zero-egress is the single biggest cost lever as the free tier gets popular.

### Pass-through COGS (NOT platform infra — belongs to [[unit-economics]])

Per-LP marginal cost is **weather-API + inference**, not platform: **~$0.0015/LP uncached → ~$0.0005 amortized** ([[unit-economics]]). 50k LP ≈ **$25–75/mo** in weather-API calls net of `(airport,hour)` caching. This is product COGS metered per prediction, tracked in [[unit-economics]], not a fixed-infra line. **Platform per-LP marginal cost ≈ $0** (inference on the already-paid always-on box; R2 read ~$0) — so the platform does **not** threaten the **$0.002/LP hard ceiling** [[unit-economics]] sets.

## Break-even (closing the [[unit-economics]] fixed-infra unknown)

- **Fixed infra ≈ $17/mo (MVP) → ~$50/mo (moderate) ≈ $200–600/yr.**
- Plus sub = **$39/yr** ([[pricing-summary]]) → **~5–15 paying Plus subscribers cover ALL fixed infra.** One B2B/API contract ($99–$1,000/mo min) covers it many times over.
- This confirms [[unit-economics]]: the free tier is safe at scale (edge = $0 backend, zero egress), and the real gate was fixed infra — now sized at **tens of dollars/month**, a trivial break-even.

## Cost-control levers (binding, per [[unit-economics]])

1. **R2 zero-egress** — keeps the public free tier's dominant cost at $0 as it scales. Non-negotiable reason to pick Cloudflare.
2. **Always-on, not scale-to-zero, for inference** — a fixed ~$11–25/mo beats paid keep-warm and meets p95 ([[hosting-options]]).
3. **`(airport,hour)` weather cache 60-min TTL** — a COGS lever, not platform, but it's what keeps per-LP under the $0.002 ceiling.
4. **Free-tier headroom monitored** — R2 read-ops and Upstash commands are the first lines to leave free; both are cheap and metered, no cliff.

## Assumptions & verification flags

- [ ] R2 Data Catalog is **public beta** — confirm GA + pricing stability before relying on the ~$0 catalog line. `#task/platform 🔼`
- [ ] Moderate-usage points (50k LP, 2 TB egress, 20M reads) are **assumed** — reset against real telemetry post-launch. `#task/platform`
- [ ] Fly cold-start / auto-stop behavior if Dagster webserver is auto-stopped — validate it wakes acceptably for occasional UI use. `#task/platform 🔽`

## Sources

Pricing rates: see [[hosting-options]] and [[orchestration-storage]] Sources (all accessed 2026-08-08). Cross-refs: [[unit-economics]] (LP cost, $0.002 ceiling, fixed-infra unknown), [[serving-service]] (metering unit), [[ingestion-backfill]] (data volumes).
