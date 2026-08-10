---
type: security
title: Security Summary — Ranked Findings & Required Controls
tags: [security, summary, moc, handoff, threat-model]
status: draft
updated: 2026-08-08
---

# Security Summary — Ranked Findings & Binding Controls

> MOC + handoff for the threat model of the predictive pivot. Detail in [[threat-model]], [[access-control]], [[abuse-and-cost]], [[privacy-compliance]]. Severity per `rules/common/code-review.md`. **CRITICAL/HIGH controls are binding requirements** on [[staff-product-engineer]] and [[staff-platform-engineer]] ([[AGENTS]] §4 dependency order).

> [!warning] Missing upstream — flagged assumption
> **No `vault/platform/*` exists** ([[staff-platform-engineer]] has not authored a note). Every network/secret/isolation control below is specified against the **`docker-compose.yml` default posture** (plaintext HTTP, `admin/admin`, unauthenticated Nessie/Postgres, public S3). If platform hardens these, downgrade accordingly — but until then, assume insecure.

## MUST-FIX BEFORE BUILD / LAUNCH (CRITICAL)

| # | Finding | Attack (input → impact) | Control | Owner | Gate |
|---|---|---|---|---|---|
| C1 | **Default creds `admin/admin` + open Nessie/PG** ([[threat-model]] TB3) | Reach S3:8333 / Nessie:19120 / PG:5432 with defaults → read/write/delete entire `raw-flights` warehouse; repoint Nessie `main` → poison all serving/edge reads | Generated secrets, no defaults; auth on Nessie/PG; private network; S3 admin off the public path | [[staff-platform-engineer]] | before build |
| C2 | **Model-artifact deserialization RCE** ([[threat-model]] TB6) | Attacker with bucket write (via C1) drops a poisoned pickle/joblib artifact → RCE in FastAPI on boot-load | Sign + checksum-verify artifacts before load; write restricted to CI identity; prefer ONNX/native (non-pickle); load sandboxed | [[staff-product-engineer]] + [[staff-ml-engineer]] | before serving |
| C3 | **API key embedded in browser client** ([[access-control]] A1) | Plus/Pro SPA ships a quota-bearing key → extracted from devtools → paid-quota + prediction theft | Consumer tiers use short-lived OIDC/OAuth session tokens; static keys B2B server-to-server only | [[staff-product-engineer]] | before paid launch |
| C4 | **Cross-tenant itinerary read (IDOR)** ([[access-control]] §4, [[threat-model]] TB7) | User B requests user A's object id / receives A's presigned URL → reads A's travel history | Tenant-prefixed storage; server-side object-level authz (deny-by-default); tenant_id from session not request; IDOR tests | [[staff-product-engineer]] | before Phase 2 |
| C5 | **GDPR rights not buildable post-hoc** ([[privacy-compliance]] §2) | No tenant partitioning → cannot satisfy Art 17 erasure / Art 15 access → regulatory + user-trust failure | Tenant-partitioned, deletion-complete data model from day 1; consent gating; DPIA (Art 35) | [[staff-product-engineer]] + legal | before Phase 2 |

## MUST-FIX BEFORE PUBLIC/PAID LAUNCH (HIGH)

| # | Finding | Control | Owner |
|---|---|---|---|
| H1 | **Anon `List` on `frontend-exports`** ([[access-control]] R2, [[threat-model]] TB1) — free enumeration of all prefixes/leaked objects | Drop `List`; `Read`-only + CDN + deterministic key convention | platform |
| H2 | **`frontend-exports` write guard** ([[access-control]] R1) — anything fresh/per-user written there is permanently ungateable | CI/write-path guard: only `{ICAO}/agg_*` + base-rate slice may land in the public bucket | product-eng |
| H3 | **Plaintext HTTP to S3 / API** ([[threat-model]] TB1/TB2) — MITM tamper of aggregates, token/URL replay | TLS everywhere; reject non-TLS | platform |
| H4 | **jsDelivr DuckDB-WASM supply chain** ([[threat-model]] TB1) — CDN/DNS compromise runs attacker JS in-page | Self-host bundle + SRI + strict CSP (`script-src 'self'`) | product-eng |
| H5 | **`read_parquet('${url}')` URL interpolation** ([[threat-model]] TB1b) — latent SQL breakout / httpfs SSRF the moment a path segment becomes user-controlled | Allowlist-validate every segment (`^[A-Z]{4}$`) before interpolation; never interpolate raw URLs | product-eng |
| H6 | **Cold-route cost amplification** ([[abuse-and-cost]] AC1) — cache-buster requests each force a paid weather fetch → margin inversion | Per-key fresh-fetch sub-budget + degrade-to-cached; distinct-`(airport,hour)` cap | product-eng |
| H7 | **No global spend circuit-breaker** ([[abuse-and-cost]] AC5) — compromised key / novel pattern runs external spend unbounded | Rolling per-key + global spend tracker; soft→degrade-to-cached, hard→shed fresh path + page ops | product-eng + platform |
| H8 | **Quota / tier bypass** ([[access-control]] A2/A3, [[abuse-and-cost]] AC2) — hit `/v1/predict` directly / forge tier claim / farm free accounts | Deny-by-default server-side tier middleware; quota keyed to trusted principal; 2-D token bucket (qps+monthly); signup friction | product-eng |
| H9 | **Prediction scraping → B2B feed theft** ([[abuse-and-cost]] AC3) | Per-key volume + scrape-breadth anomaly; `snapshot_id` provenance; ToS | product-eng |
| H10 | **PII in prediction/Dagster logs** ([[privacy-compliance]] §4) — logs reconstruct travel history | No raw itinerary/flight logging; pseudonymize principal; scrub traces; short retention + access control | product-eng + platform |
| H11 | **Co-located public + private storage** ([[threat-model]] TB3) — one S3 authz slip exposes raw per-flight data | Separate public edge origin (CDN/bucket) from private warehouse endpoint | platform |

## LATER HARDENING (MEDIUM / LOW)

- **M1** Zip-bomb / oversized-archive on BTS ingest ([[abuse-and-cost]] AC7 / [[threat-model]] TB4) — bounded decompression + checksum.
- **M2** Untrusted external-response XSS (NOTAM free-text → `reason_codes` → SPA) ([[threat-model]] TB5) — schema-validate + escape on render.
- **M3** Upload parser abuse (CSV-formula-injection, JSON-bomb, SSRF-via-URL, `read_csv` on untrusted bytes) ([[abuse-and-cost]] AC7) — caps + sanitize-on-export + no server fetch of user URLs (block 169.254.169.254/RFC1918).
- **M4** Edge egress wallet attack ([[abuse-and-cost]] AC6) — CDN long-TTL cache + per-IP/ASN bandwidth caps.
- **M5** ePrivacy cookie consent on anonymous tier ([[privacy-compliance]] §5).
- **M6** Cross-border transfer / EU-region hosting for personal data ([[privacy-compliance]] §6) — depends on platform.
- **M7** Bot defense on signup/login ([[abuse-and-cost]] AC4).
- **L1** Input-validation DoS on `/v1/predict` (bad ICAO/datetime/batch length) ([[abuse-and-cost]] AC8) — strict Pydantic bounds.
- **L2** BTS data-poisoning via malformed rows ([[threat-model]] TB4) — dbt `unique`/range tests as a security control.

## Handoffs (binding)

### → [[staff-product-engineer]]
Fold into the serving/data design as **requirements, not options**: C2 (artifact signing), C3 (token model), C4 (tenant authz), C5 (deletion-complete model), H2/H4/H5 (bucket write-guard, self-host WASM, path allowlisting), H6/H7/H8/H9 (cost breaker + degrade + 2-D token bucket + scrape caps), H10 (PII-safe logging), M1–M3/L1–L2 as backlog. Recommend: **proxy private reads through FastAPI instead of vending presigned URLs** ([[access-control]] §3).

### → [[staff-platform-engineer]] (note not yet written — assumption flagged)
C1 (no default creds; Nessie/PG/S3 auth + isolation), H1/H3/H11 (drop anon List, TLS, CDN, split public/private storage), H7 (spend metrics), H10/M6 (log store + hosting region/transfer safeguards), Art 33 breach monitoring. **When your note lands, confirm or refute these assumptions.**

### → [[sales]] / [[staff-product-engineer]]
Abuse limits in [[abuse-and-cost]] §3 are derived from [[unit-economics]] ($0.002/LP ceiling, Pro fair-use inversion) — reconcile the proposed per-tier caps with the final [[tier-matrix]].

## Files written (this pass)
`vault/security/`: [[threat-model]], [[access-control]], [[abuse-and-cost]], [[privacy-compliance]], [[security-summary]].

## Sources
- Repo: `docker-compose.yml`, `.env.example`, `frontend/src/db/{client,queries}.ts` — accessed 2026-08-08
- Vault: [[serving-service]], [[frontend-backend-split]], [[iceberg-duckdb]], [[ingestion-backfill]], [[feature-contract]], [[product-shape-by-tier]], [[architecture-summary]], [[unit-economics]], [[metering-unit]]; `tech_product_Architecture.txt` — accessed 2026-08-08
- OWASP Top 10 (2021), OWASP API Security Top 10 (2023), OWASP ASVS v4, GDPR (EU) 2016/679, ePrivacy 2002/58; `rules/*/security.md`, `rules/common/code-review.md`
