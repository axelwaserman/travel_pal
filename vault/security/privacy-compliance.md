---
type: security
title: Privacy & Compliance — GDPR, Retention, PII
tags: [security, privacy, gdpr, compliance, pii, retention]
status: draft
updated: 2026-08-08
---

# Privacy & Compliance

> Personal travel history (Phase 2) is sensitive; EU is the stronger market ([[research-summary]] finding 5, EU261 angle in [[unit-economics]]). GDPR + ePrivacy obligations and the controls that satisfy them. Consumes [[access-control]] (tenant isolation is the technical backbone of most rights here). Feeds [[security-summary]]. Standards cited: GDPR (Regulation 2016/679) articles inline; ePrivacy Directive 2002/58.

## 1. What personal data exists, and when

| Data | Phase | Sensitivity | GDPR basis |
|---|---|---|---|
| Anonymous edge usage (IP, device, query params) | Now | Low but IP = personal data (Art 4(1); *Breyer* C-582/14) | legitimate interest / consent for non-essential cookies (ePrivacy) |
| Account identity (email, auth) | Phase 2 | Medium | contract (Art 6(1)(b)) |
| **Uploaded itineraries + travel history** | Phase 2 | **High** — reveals home base, patterns, dates, presence/absence at home | consent (Art 6(1)(a)) or contract; explicit, granular |
| Prediction request logs (flight + user) | Phase 2 | Medium-High — same inference risk | minimize; see §4 |

> Travel patterns are not a special category (Art 9) per se, but are **highly re-identifying** and reveal routine/location — treat with special-category-level care.

## 2. Data-subject rights (must be technically supported before Phase 2) · CRITICAL

Each right maps to a concrete control that depends on tenant isolation ([[access-control]] T1–T5):

| Right | Article | Control required |
|---|---|---|
| Access / portability | Art 15, Art 20 | export all `tenants/{tenant_id}/*` + derived data as machine-readable (CSV/JSON) via authenticated request |
| **Erasure ("right to be forgotten")** | Art 17 | delete object(s) **+ derived features + Redis cache entries + logs** for that tenant — deletion must propagate everywhere ([[access-control]] T5). A backup/Iceberg copy that can't be purged is a violation risk. |
| Rectification | Art 16 | allow re-upload/correction |
| Restriction / objection | Art 18, 21 | flag to suspend processing |
| Automated-decision transparency | Art 22 | prediction is decision-*support*, not solely-automated legal effect — **but** if EU261/insurance actions ([[unit-economics]]) trigger automatically off a prediction, Art 22 engages → keep a human/user in the loop and document logic. Our `reason_codes[]` ([[feature-contract]] §C) already aids the "meaningful information about the logic" duty. |

**Requirement:** these are not roadmap items to add later — Art 17/15 must be buildable from day one of Phase 2, which means the **data model must be tenant-partitioned and deletion-complete by design** ([[access-control]]).

## 3. Core GDPR principles → design constraints

- **Lawful basis + consent (Art 6, 7):** explicit opt-in before itinerary upload; granular (upload ≠ marketing ≠ affiliate hand-off). The **affiliate/insurance hand-off** in [[unit-economics]] is a **separate purpose** — needs its own consent and a data-processing/sharing agreement with the partner (Art 44+ if partner is outside EEA).
- **Data minimization (Art 5(1)(c)):** upload only fields the prediction needs; don't ingest full PNRs/passport/payment if not required.
- **Purpose limitation (Art 5(1)(b)):** itinerary data used for the user's predictions — not silently folded into the training spine. If used for model training, that's a distinct purpose → separate consent + anonymization/aggregation first.
- **Storage limitation (Art 5(1)(e)) / retention:** define TTLs — e.g. itineraries purged N months after trip unless the user keeps them; prediction logs retained only as long as needed for abuse/billing. **No indefinite retention.** (Set concrete N with legal — flagged, do not invent.)
- **Storage of BTS/aggregate data:** public-domain, non-personal → out of scope. Good.

## 4. PII in logs & telemetry · HIGH
- **Risk:** `/v1/predict` logs of `(user, flight_number, route, datetime)` reconstruct a user's travel history in the logging system — a second, often-unprotected copy of the sensitive data. Same for Dagster run logs, Redis keys embedding user ids, and error traces.
- **Controls:** never log raw itinerary contents; pseudonymize the principal in logs (opaque id, not email); scrub request bodies from error traces; short log retention; access-control the log store; keep tenant id out of any shared/public metric labels.

## 5. ePrivacy / cookies (anonymous tier, live now) · MEDIUM
- Non-essential cookies/analytics/affiliate tracking need a **consent banner** (ePrivacy Directive; EU). Essential-only by default; no tracking before consent. IP-based rate-limiting/abuse defense is legitimate interest (document it).

## 6. Cross-border & hosting · MEDIUM (depends on [[staff-platform-engineer]])
- If serving EU users from **US-hosted** infra, personal data leaves the EEA → need transfer safeguards (SCCs, Art 46) or EU-region hosting. **Flagged: no `vault/platform/*` — hosting region unknown.** Recommend **EU-region hosting for personal data** given the EU-first GTM ([[research-summary]]/[[unit-economics]]).

## 7. Compliance backlog (records & governance)
- **RoPA (Art 30):** maintain records of processing.
- **DPA/DPIA (Art 35):** the itinerary feature (profiling of travel behaviour, potential automated action) likely warrants a **DPIA** before Phase 2 launch.
- **Breach notification (Art 33/34):** 72-hour process; depends on logging/monitoring from [[staff-platform-engineer]].
- **Processor agreements (Art 28):** with weather/flight-feed vendors and the affiliate/insurer partner.

## Binding requirements
- **[[staff-product-engineer]] MUST** build tenant-partitioned storage + complete-deletion (Art 17/15/20 support), consent gating on upload + affiliate hand-off, data minimization, and PII-safe logging **as Phase-2 acceptance criteria**.
- **[[staff-platform-engineer]] MUST** confirm hosting region + transfer safeguards, log-store access control + retention, and breach-monitoring. **Flagged: no platform note exists.**
- **Human/legal MUST** set concrete retention periods, run the DPIA, and sign vendor/affiliate DPAs — **do not invent these values** ([[AGENTS]] rule 2).

## Sources
- GDPR (Regulation (EU) 2016/679) Art 4,5,6,7,9,15,16,17,18,20,21,22,28,30,33,34,35,44,46; ePrivacy Directive 2002/58/EC; CJEU *Breyer* C-582/14 (IP = personal data) — accessed 2026-08-08
- [[research-summary]] (EU-first, EU261), [[unit-economics]] (affiliate/insurance angle), [[feature-contract]] (reason codes), [[access-control]] (tenant isolation), [[threat-model]] TB7 — accessed 2026-08-08
- OWASP Top 10 (2021) A09 (logging); `rules/common/security.md`, `rules/web/security.md`
