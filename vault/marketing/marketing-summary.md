---
type: marketing
title: Marketing Summary & Brand System — FlightPal (B2C)
tags: [marketing, brand, summary, moc, handoff]
status: draft
updated: 2026-08-10
---

# Marketing Summary & Handoff

> **Rev. per PR #13.** One-page synthesis of [[naming]], [[positioning]], [[messaging]], [[lead-gen-plan]] + brand-system sketch. **B2C-only** (B2B feed dropped). Grounded in [[research-summary]], [[personas]] (P1/P2), [[demand-evidence]], [[differentiation-thesis]] and [[sales]] ([[tier-matrix]]). Handoffs to [[staff-product-engineer]] and [[staff-ml-engineer]].

## Recommendation in three sentences

Rename to **FlightPal** (endorsing the human's lean — memorable, owns the "flight" category, fits the friendly B2C tone), **conditional on clearing an existing `tryflightpal.com` collision**; fallback **Glasswing**. Lead every surface with the **outcome** — *"Pick the flight that won't wreck your trip"* — ranking a route's options by reliability, **connection safety**, and **which aircraft/cabin** you'll fly, with transparency demoted to a supporting trust cue. Grow B2C through a **Chrome extension** that grades flights inline at the booking moment, plus long-tail SEO and community — near-zero paid spend — funneling into the consumer ladder (Free limited-mode → Plus → Pro).

## Key decisions

- **Name:** primary **FlightPal** (blocking check: the live fear-of-flying app on the same name); fallback **Glasswing**. All availability = checks to run, none verified ([[naming]]).
- **Positioning pivot:** outcome/decision-led ("best flight for your route"), **not** transparency-led, **not** accuracy. Stop naming competitors in user-facing copy.
- **New product angles:** **connection-miss risk** (leg 1 late vs leg 2 on time) and **aircraft/cabin quality via tail assignment** — both fed by daily forward ingestion.
- **B2B removed:** no feed, no TMC/insurer personas, no B2B channel. Consumer-only.
- **MVP:** limited mode, **5 free searches/day**.

## ⚠️ FLAGGED (surfaced, not silently rewritten)

The review asked to **"guarantee"** the **"best flight for your buck"** and claim we're **"the only service"** that ensures it. I actioned the *direction* (confident, outcome-first) but did **not** write those literal words, because:
1. **"guarantee/ensures"** on a probabilistic product implies an undefined remedy + ad-substantiation/legal risk, and reopens the accuracy trap → use *"the flight least likely to let you down,"* or scope a **defined, bounded** service guarantee with legal.
2. **"for your buck"** = a price/value claim, but **we ingest no fare data** (spine is on-time + weather/NOTAM) → unsubstantiable → use *"best flight for your trip."*
3. **"the only service"** = a uniqueness/superiority claim requiring proof → use *"the simplest way to pick the flight that won't wreck your trip."*
Detail + honest alternatives in [[positioning]] "Claims guardrail." If a hard guarantee is still wanted, scope a real SLA-style promise, not an open-ended one.

## Lead-gen headline

- **Hero:** **"Pick the flight that won't wreck your trip."** — *sub:* "FlightPal reads a decade of on-time data, live conditions, connection risk, and which aircraft you'll actually fly — then tells you the best option for your route."

## Brand system sketch (direction only — not final design)

Respecting `rules/web/design-quality.md` (intentional, non-template):

- **3 adjectives:** **Confident · Clear · Friendly.**
- **Tone of voice:** plain over clever; lead with the pick, keep the "why" one tap away; confident about the recommendation, honest about certainty (things change; we show the current best).
- **Visual direction:** a **decision/grading** system — flight options shown as a ranked, scannable comparison with a clear "best pick" call-out; an at-a-glance **reliability + aircraft + connection** grade (badge/meter) as the hero device; data-viz as a first-class design element, not an afterthought. Depth via layering, not uniform cards.
- **Type:** a characterful humanist sans/serif for headlines paired with a precise grotesk/mono for grades & numbers — a deliberate pairing.
- **Color:** light base (do **not** auto-default to dark); one disciplined semantic scale for good→risky grades, used consistently across the extension + app.
- **Motion:** compositor-friendly only; motion clarifies the ranking/decision, never decorates.
- **Hand off** to whoever builds the extension + landing page.

## Files written / revised (this deliverable)

- [[naming]] — FlightPal evaluation + recommendation (conditional) + blocking collision check; Glasswing fallback
- [[positioning]] — outcome-led wedge, statement, claims guardrail (flag), competitor de-emphasis
- [[messaging]] — B2C persona props, connection-miss + aircraft/cabin angles, hero + benefit lines
- [[lead-gen-plan]] — Chrome-extension surface, SEO/community, B2C funnel (B2B dropped)
- [[marketing-summary]] — this note + brand-system sketch

## Handoffs

- → [[staff-product-engineer]]: **Chrome-extension** inline grading surface (on Google Flights/OTAs); **tail-assignment** data for cabin grade; **connection-miss** scoring inputs; public route pages (server-render first, DuckDB-WASM edge is nice-to-have); first-party analytics + activation instrumentation; free limited-mode (5/day) flow.
- → [[staff-ml-engineer]]: confirm **"best-pick" ranking**, **connection-miss** scoring, and **tail-assignment** tracking are feasible/defensible from the forward-ingestion spine; keep honesty guardrails.
- → [[sales]]: consumer tiers only; marketing sets **no prices**.

## Open tasks

- [ ] Run collision + trademark/domain/app-store/social checks on **FlightPal** (fallback Glasswing) #task/marketing 🔺 📅 2026-08-22 ⛓ [[naming]]
- [ ] Validate feasibility of tail-assignment + connection-miss data w/ [[staff-ml-engineer]] before promising them in copy #task/marketing 🔺 📅 2026-09-15 ⛓ [[staff-ml-engineer]]
- [ ] Decide with legal whether any bounded service-guarantee is offerable #task/marketing 🔼 📅 2026-09-15
- [ ] A/B the 3 alt hero headlines once the funnel is live #task/marketing 🔼 📅 2026-09-30

## Sources

- All external claims cited in the linked notes (name collision, SEO volumes, disruption stats) with access dates 2026-08-08 / 2026-08-10.
- Cross-refs: [[naming]], [[positioning]], [[messaging]], [[lead-gen-plan]], [[research-summary]], [[personas]], [[tier-matrix]], [[differentiation-thesis]]
