---
type: security
title: Abuse & Cost — Rate Limits, Bot Defense, Spend Circuit-Breaker
tags: [security, abuse, cost, rate-limit, dos, scraping, unit-economics]
status: draft
updated: 2026-08-08
---

# Abuse & Cost Attacks

> The free tier triggers real marginal cost (weather API, inference) and the edge is anonymous. Model quota-exhaustion, cost-amplification, and scraping attacks; specify limits tied to [[metering-unit]] + [[unit-economics]]. Consumes [[serving-service]] §rate-limiting. Feeds [[security-summary]]. Standards: OWASP A04 (Insecure Design), API4:2023 (Unrestricted Resource Consumption).

## 1. The cost surface (from [[unit-economics]])

- **1 LP** = a fresh-signal fetch + inference. Blended cost **~$0.0015/LP**; **hard ceiling $0.002/LP** ([[unit-economics]] handoff). Cold `(airport,hour)` pays full OpenWeather fetch; hot hub-hour ≈ $0 (60-min cache).
- Edge descriptive reads = **$0 backend compute** but **non-zero egress** ([[metering-unit]] Class A).
- Free tier gets **no** prediction endpoint ([[product-shape-by-tier]]) — good, it removes the worst amplification vector at the source. **Pro fair-use inversion** is called out as margin-negative in [[unit-economics]] risk #5 and is a *security* control, not just billing.

## 2. Attacks (input → impact → control)

### AC1 — Cold-route cost amplification (cache-buster) · HIGH
- **Attack:** an authenticated Plus/Pro (or trial) caller requests predictions across a rotating set of **rare `(carrier,origin,dest,hour)`** tuples, each a cold `(airport,hour)` → each forces a **fresh OpenWeather fetch (~$0.0015)**. N distinct cold requests ≈ N × full cost, defeating the amortization the whole margin model assumes.
- **Impact:** direct spend attack; drives blended cost toward/over the $0.002 ceiling; margin inversion at scale.
- **Controls:** (a) **degrade-to-cached / base-rate-only** once a per-key *fresh-fetch* sub-budget is exceeded (distinct from the LP count) — never serve at a loss ([[unit-economics]] handoff); (b) cap **distinct `(airport,hour)` fetches per key per window**, not just LP count; (c) global **spend circuit-breaker** (AC5).

### AC2 — Quota exhaustion / free-rider on paid endpoints · HIGH
- **Attack:** hit `/v1/predict` beyond entitlement, or spin many free accounts (trial LP cap 5/day, [[unit-economics]]) to farm predictions for free; or hammer alert re-evaluations (each re-score = 1 LP, [[metering-unit]]).
- **Controls:** **Redis token bucket** per authenticated principal — *per-second qps* **and** *monthly quota* ([[serving-service]] already specifies this; make both dimensions mandatory). `429 + Retry-After` on breach; `quota_remaining` in `meta`. **Alert watchlists capped** (max active watches/tier) since each drives recurring cost. Signup friction on free/trial (email verify + device/bot signal, AC4) to stop mass-account farming.

### AC3 — Prediction scraping (B2B revenue theft) · HIGH
- **Attack:** systematically enumerate routes/times against `/v1/predict` (or `/v1/routes/{o}/{d}/reliability`) to **reconstruct the calibrated feed** — the paid B2B product ([[product-shape-by-tier]]) — then resell/self-host. Erodes the margin story.
- **Controls:** per-key **rate + monthly volume caps** sized so full-catalog scrape is economically infeasible within a tier; anomaly detection on breadth (many distinct routes, low repeat); ToS + per-response watermark/`snapshot_id` provenance ([[serving-service]] meta) for attribution; consider query-shape limits on `batch`.

### AC4 — Bot / automated abuse on anonymous + signup surfaces · MEDIUM
- **Attack:** bots scrape the edge en masse (AC6), farm free accounts (AC2), or credential-stuff the login (Phase 2).
- **Controls:** bot defense that isn't heavy-handed CAPTCHA-by-default (`rules/web/security.md`): prefer edge rate-limiting + honeypot + proof-of-work/managed challenge only on suspicious signals; rate-limit + lockout + breached-password check on login (OWASP A07).

### AC5 — Missing global spend circuit-breaker · HIGH (before paid launch)
- **Gap:** no design element caps **aggregate** external-API spend. A single compromised key or a novel amplification pattern can run OpenWeather/paid-feed cost unbounded before anyone notices.
- **Control (binding):** a **spend circuit-breaker**: track rolling external-API + inference spend (per-key and global) against budget thresholds; at soft threshold → **force degrade-to-cached / base-rate-only for all**; at hard threshold → **shed the fresh-fetch path** (serve stale base rates, `confidence=low`) and page ops. Ties directly to the [[unit-economics]] $0.002/LP ceiling. This is the backstop for AC1/AC2/AC3.

### AC6 — Edge egress wallet attack · MEDIUM
- **Attack:** anonymous scripted full-file GETs across every `{ICAO}/*.parquet` (aided by the anon `List` grant, [[threat-model]] TB1) → CDN/egress bill amplification (data is public-domain so no confidentiality loss, but $ loss).
- **Controls:** mandatory **CDN with long-TTL immutable caching** in front of the bucket (content is versioned/immutable — ideal); per-IP/ASN bandwidth caps at the CDN; drop anon `List` so scrapers can't cheaply enumerate ([[access-control]] R2).

### AC7 — Upload parser resource abuse (Phase 2) · MEDIUM
- **Attacks:** **zip bomb** (if archives accepted) → CPU/disk DoS; **billion-laughs/deeply-nested JSON** → parser OOM; **huge CSV** → memory blow-up; **CSV formula injection** (`=`,`+`,`-`,`@` leading cells) → code exec when a user later exports and opens in Excel/Sheets; **SSRF** if an itinerary field contains a URL the backend fetches; **DuckDB `read_csv` on untrusted bytes**.
- **Controls:** size + row + column + nesting-depth caps; reject archives at the itinerary endpoint ([[access-control]] §5); stream-parse with bounded memory; **sanitize CSV cells on export** (prefix `'` or block formula-leading chars) per OWASP CSV-injection guidance; **no server-side fetch of user-supplied URLs** (or strict allowlist + block link-local/metadata IPs 169.254.169.254 / RFC1918 to kill SSRF, OWASP A10); validate every field with Pydantic before it reaches DuckDB.

### AC8 — Input-validation DoS on `/v1/predict` · LOW-MEDIUM
- **Attack:** absurd `scheduled_departure` (year 9999), malformed ICAO/IATA, huge batch arrays → wasted resolve/compute.
- **Controls:** Pydantic strict validation — ICAO `^[A-Z]{4}$`, IATA `^[A-Z0-9]{2,3}$`, datetime within a sane window (e.g. now-1d … now+1y), **bounded `batch` array length**. Reject fast (`serving-service` "validate < 15 ms").

## 3. Rate-limit / cost-control matrix (proposed; reconcile with [[sales]])

| Surface | Limit (proposed) | Enforcement | Ties to |
|---|---|---|---|
| Anonymous edge (Parquet) | per-IP/ASN bandwidth cap; CDN cache | CDN/WAF | AC6 |
| Free/trial account | 5 LP/day (already), N accounts/device | token bucket + signup friction | [[unit-economics]], AC2/AC4 |
| Plus | monthly quota + qps; alert-watch cap | Redis token bucket | AC2 |
| Pro | **500/day soft cap + degrade-to-cached** (mandatory, not optional) | token bucket + degrade | [[unit-economics]] risk #5, AC1 |
| B2B API | per-key volume + qps + scrape-breadth anomaly | token bucket + anomaly | AC3 |
| Global | **spend circuit-breaker** (soft→degrade, hard→shed fresh path) | spend tracker | AC5, $0.002/LP ceiling |
| Fresh-fetch sub-budget | distinct `(airport,hour)`/key/window cap | counter | AC1 |

## Binding requirements
- **[[staff-product-engineer]] MUST** implement AC5 (spend circuit-breaker), AC1 degrade-to-cached, the two-dimensional token bucket (qps + monthly), AC3 scrape caps, AC7/AC8 input validation. Pro soft-cap + degrade is **mandatory** (margin-inversion risk).
- **[[staff-platform-engineer]] MUST** provide CDN + WAF/edge rate-limiting (AC4/AC6) and metrics for the spend breaker. **Flagged: no `vault/platform/*` yet.**

## Sources
- [[unit-economics]] ($0.0015–0.002/LP, Pro fair-use inversion, degrade-to-cached), [[metering-unit]] (LP defn, caching amortization), [[serving-service]] (token bucket), [[product-shape-by-tier]] (free=edge-only), [[threat-model]] TB1/TB4/TB7 — accessed 2026-08-08
- [OpenWeather One Call 3.0 ~$0.0015/call](https://openweathermap.org/api/one-call-3) — accessed 2026-08-08 *(measured, via [[unit-economics]])*
- OWASP Top 10 (2021) A04/A10; OWASP API Security Top 10 (2023) API4 (Unrestricted Resource Consumption); OWASP CSV Injection; `rules/web/security.md` (bot defense stance)
