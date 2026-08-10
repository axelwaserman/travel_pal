---
type: security
title: Access Control — AuthN/AuthZ, Presigned URLs, Multi-Tenant
tags: [security, access-control, authn, authz, presigned, multi-tenant, idor]
status: draft
updated: 2026-08-08
---

# Access Control — AuthN/AuthZ, Presigned URLs, Multi-Tenant Isolation

> Controls for TB2/TB3/TB7 in [[threat-model]]. Consumes [[serving-service]] (metering seam), [[frontend-backend-split]] (physical boundary), [[product-shape-by-tier]] (tiers). Feeds [[security-summary]]. Standards: OWASP A01 (Broken Access Control), A07 (Auth Failures), ASVS v4 §2/§4.

## 1. Direct object-storage exposure (the legacy premise, re-examined)

`tech_product_Architecture.txt` §3.3 vends **presigned URLs** so DuckDB-WASM reads byte-ranges directly. The current design ([[frontend-backend-split]]) *avoids* this for the free tier by making `frontend-exports` **anonymous-public** — which is only safe **because the content is public-domain aggregate BTS**. Two binding rules follow:

- **R1 (CRITICAL, before build):** The public bucket may contain **only** stale, public, aggregate data. **Nothing** fresh, per-flight, per-user, or metered may ever be written to `frontend-exports` — enforce with a CI/write-path guard (deny writes whose key isn't `{ICAO}/agg_*` or the base-rate slice), not just convention. Rationale: anything there is ungateable and permanently cacheable. (Confirms [[frontend-backend-split]] §"Why gating must be server-side".)
- **R2 (HIGH, before public launch):** Drop the anonymous **`List`** grant (`.env.example` currently `-actions=Read,List`). `List` = free enumeration of every airport prefix and any leaked object. Use `Read` only, front the bucket with a CDN, and rely on a **published, deterministic key convention** (`{ICAO}/route_timeliness.parquet`) so clients never need to list. → [[threat-model]] TB1.

## 2. AuthN / AuthZ model (metered API)

Current design states only "API-key → tier lookup → token bucket" ([[serving-service]] §rate-limiting). Gaps + requirements:

| # | Requirement | Sev | Rationale |
|---|---|---|---|
| A1 | **No static API key in any browser client.** Consumer Plus/Pro auth = user login (OIDC/OAuth2) → backend mints a **short-lived (≤15 min) access token**; the browser never holds a long-lived, quota-bearing secret. Static keys are **B2B server-to-server only**, stored server-side. | CRITICAL | A key in the SPA is trivially extracted → paid-quota + prediction theft ([[threat-model]] TB2). OWASP A07. |
| A2 | **Server-side tier enforcement on every route** (deny-by-default middleware): tier → allowed endpoints + quota. Free tier is issued **no** prediction credential (edge-only, [[product-shape-by-tier]]). | CRITICAL | Client-side gating is bypassable; free→paid escalation by hitting `/v1/predict` directly must 403. OWASP A01. |
| A3 | **Bind quota to a server-trusted identity**, never to a client-supplied `user_id`/tier claim. Quota counter keyed on the authenticated principal in Redis; tier read from the DB, not the token body, unless the token is signed and validated. | HIGH | Prevents "set `tier=pro` in the request" and quota-reset by rotating a client-chosen id. |
| A4 | **API keys: hashed at rest, prefixed, rotatable, revocable, scoped.** Store `sha256(key)`, show once. Per-key scope = tier + endpoint set. Support rotation without downtime and immediate revocation. | HIGH | Key leakage is inevitable; limit blast radius + enable kill. |
| A5 | **TLS everywhere + short token TTL** to kill replay ([[threat-model]] TB2). Reject non-TLS. | HIGH | |
| A6 | **Nessie + Postgres + SeaweedFS admin behind auth + private network**; no default creds (see [[threat-model]] TB3, requirement on [[staff-platform-engineer]]). | CRITICAL | Unauthenticated Nessie = catalog repoint = data poisoning. |

## 3. Presigned-URL vending (becomes live in Phase 2 — private per-user data)

When per-user history lands, the free-tier anon model no longer applies to that data. If presigned URLs are used (legacy §3.3), they MUST satisfy:

| Property | Requirement | Failure if violated |
|---|---|---|
| **Scope** | One URL grants read to **exactly one object key** under the caller's tenant prefix (`tenants/{tenant_id}/...`). No wildcard/prefix grants, no bucket-level. | Prefix grant → enumerate/read all tenants (IDOR, A01). |
| **TTL** | ≤ **60–300 s**, just enough for DuckDB-WASM to issue the range read. | Long TTL → shareable/loggable link becomes a durable capability. |
| **Method** | `GET` only; never `PUT`/`LIST` in a client-vended URL. | Write/list capability leaks to the client. |
| **Binding** | Sign server-side **only after** authz check that the authenticated principal owns that key. Never derive the key from a client-supplied path. | Client passes another tenant's key → server signs it → IDOR. |
| **Transport** | HTTPS-only; the signature must not be usable over plain HTTP. | MITM lifts the signed URL and replays within TTL. |
| **Replay** | Accept that within TTL a URL is replayable — keep TTL tiny; do not embed in anything cacheable/shared; log vend events for abuse detection. | — |

> **Preferred alternative (recommend to [[staff-product-engineer]]):** for private data, **proxy the read through FastAPI** (server runs the DuckDB query, returns compact JSON — the legacy "compute proxy" concept, kept in [[frontend-backend-split]]) instead of vending object-storage URLs to the browser at all. Removes the entire presigned-URL scope/TTL/replay class. Vend presigned URLs only where payload size makes proxying impractical.

## 4. Multi-tenant isolation (Phase 2 personal itineraries) — CRITICAL before Phase 2

Concrete failure: user A uploads `itinerary.csv`; user B calls `GET /v1/history/{id}` or receives a presigned URL for A's object → reads A's travel history (home routes, patterns, dates). This is **IDOR / broken object-level authz** (OWASP A01, the #1 category).

Required controls:
- **T1 — Tenant-prefixed storage:** every uploaded object at `tenants/{tenant_id}/{obj}`; `tenant_id` from the **authenticated session**, never from the request body/path.
- **T2 — Object-level authz on every access:** check `principal.tenant_id == object.tenant_id` on read/delete/predict, server-side, deny-by-default. Add automated IDOR tests (A requests B's ids → 403/404).
- **T3 — Query isolation:** any DuckDB/serving query over personal data is filtered by `tenant_id` as a **bound parameter**; never interpolate ids into SQL/paths ([[threat-model]] TB1b). One shared connection must not leak rows across tenants.
- **T4 — No cross-tenant cache keys:** Redis quota/response caches keyed with `tenant_id` in the key; base-rate cache (non-personal) stays shared.
- **T5 — Deletion propagation:** erasure (see [[privacy-compliance]]) must remove the object, derived features, cache entries, and logs for that tenant.

## 5. Upload handling (authz-adjacent; parser abuse detailed in [[abuse-and-cost]])
- Authenticated users only; size cap; MIME/extension allowlist (`.csv`/`.json`); reject archives at the itinerary endpoint (no zip → no zip bomb here).
- Store under the tenant prefix with a **server-generated** filename (defeat path traversal `../` in client filename).
- Parse in a sandboxed worker with row/column/size limits; treat every field as untrusted (see [[abuse-and-cost]] §uploads for CSV-formula-injection, SSRF-via-URL, zip-bomb specifics).

## Binding requirements (stated as such)
- **[[staff-product-engineer]] MUST** implement A1–A5, R1, T1–T5, and prefer §3 proxy-read over presigned URLs. These are not suggestions — they gate paid launch (A1/A2) and Phase 2 (T1–T5).
- **[[staff-platform-engineer]] MUST** implement A6 (no default creds, Nessie/PG/S3 auth + isolation, TLS/CDN for R2). **Flagged: no `vault/platform/*` exists — securing against the compose default posture.**

## Sources
- Repo: `.env.example` (anon Read,List), `docker-compose.yml` (default creds), `frontend/src/db/queries.ts` — accessed 2026-08-08
- `tech_product_Architecture.txt` §3.3 (presigned URLs) — accessed 2026-08-08
- [[serving-service]], [[frontend-backend-split]], [[product-shape-by-tier]], [[threat-model]] — accessed 2026-08-08
- OWASP Top 10 (2021) A01/A07; OWASP ASVS v4 §2 (Auth), §4 (Access Control); `rules/web/security.md`
