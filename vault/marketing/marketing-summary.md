---
type: marketing
title: Marketing Summary & Brand System — TravelPal → Glasswing
tags: [marketing, brand, summary, moc, handoff]
status: draft
updated: 2026-08-08
---

# Marketing Summary & Handoff

> One-page synthesis of [[naming]], [[positioning]], [[messaging]], [[lead-gen-plan]] + the brand-system sketch. Grounded in [[research-summary]], [[competitors]], [[personas]], [[differentiation-thesis]] and [[sales]] ([[tier-matrix]], [[pricing-summary]]). Handoffs to [[staff-product-engineer]] and [[staff-ml-engineer]].

## Recommendation in three sentences

Rename **TravelPal → Glasswing** — a name whose glass-box metaphor *is* our wedge: **transparency + route-shopping + cost-to-serve, never accuracy** (we won't out-predict Google/FlightAware Foresight, [[differentiation-thesis]]). Lead every surface with *"Know which flight to trust — and see exactly why,"* give away the transparent route-reliability analytics free (the ~$0 edge tier is the acquisition engine), and funnel into the [[sales]] ladder (Free → Plus → Pro → Team/API), where the **B2B auditable feed is the margin**. Grow through a public **Delay Almanac** stats page (SEO + PR) plus high-signal community and B2B thought-leadership — near-zero paid spend.

## Key decisions

- **Name:** primary **Glasswing**; fallback **Truebound** / **Almanac**-compound. Avoid **Foresight / Wingman / Skylark / FlightCaster / FlyWise** (collisions/baggage — [[naming]]). *All availability = checks to run, none verified.*
- **Wedge:** transparent, auditable, route-level, cheap. Position in the open **transparent × route/portfolio** quadrant ([[positioning]] grid).
- **Honesty (binding):** probabilistic/calibrated language only; uncertainty bands shown as a feature; no guarantees; never repeat the fabricated "89.3%/MIT/7.2B" Google stats. Coordinate public accuracy claims with [[staff-ml-engineer]].
- **Geo:** lean **EU** for the action/insurance angle (EU261 > withdrawn US DOT rule).

## Lead-gen headline (for landing + B2B)

- **B2C hero:** **"Know which flight to trust."** — *sub:* "Glasswing reads a decade of on-time data and live conditions to tell you how reliable a route really is — method shown, odds honest, analytics free."
- **B2B one-liner:** *"An auditable flight-delay risk feed — calibrated, backtested, and priced for mid-market, not just enterprises."*

## Brand system sketch (direction only — not final design)

Respecting `rules/web/design-quality.md` (intentional, non-template; no default card-grid/gradient-blob hero):

- **3 adjectives:** **Transparent · Precise · Calm.**
- **Tone of voice:** plain over clever, specific over hype; confident about transparency & cost, humble about certainty. Every number ships with its band and its reason.
- **Visual direction:** *glass-box editorial* — layered translucent surfaces (frosted/glass panels over data), the **Glasswing** transparent-wing motif as a recurring device, and **data-visualization treated as the hero** (reliability distributions, calibration/reliability curves shown openly — the "we show our work" proof, rendered by the existing DuckDB-WASM dashboards). Depth via overlap & translucency, not drop-shadow uniformity.
- **Type:** a characterful humanist or editorial serif for headlines paired with a precise grotesk/mono for data — a deliberate pairing, not a default stack. Mono for numbers/odds signals rigor.
- **Color:** light-luxury base (do **not** auto-default to dark mode); one disciplined accent for the "reliable/at-risk" semantic scale used consistently across viz — color as meaning, not decoration.
- **Motion:** compositor-friendly only (`transform`/`opacity`); motion clarifies the forecast (band widening under uncertainty), never decorates.
- **Hand off** to whoever builds the landing page ([[lead-gen-plan]] stats page + hero); do not finalize here.

## Files written (this deliverable)

- [[naming]] — 7 candidates + AVOID list + recommendation (Glasswing) + checks-to-run
- [[positioning]] — wedge, positioning statement, competitor grid, honesty guardrails
- [[messaging]] — persona/tier value props, hero + subhead + 3 benefit lines, B2B one-liner
- [[lead-gen-plan]] — funnel w/ per-stage goals, Delay Almanac SEO engine, channels, attribution
- [[marketing-summary]] — this note + brand-system sketch

## Handoffs

- → [[staff-product-engineer]]: public **Delay Almanac** = programmatic SEO route/airport/carrier pages on the DuckDB-WASM edge; first-party privacy-respecting analytics + funnel/activation instrumentation (respect `rules/web/security.md` CSP); free-alert signup flow.
- → [[staff-ml-engineer]]: validate that public **calibration/backtest** claims are defensible before they ship (the transparency promise must be real); confirm uncertainty-band presentation.
- → [[sales]]: B2B thought-leadership + design-partner pipeline feed the Team/API price/calibration validation ([[pricing-summary]] open Qs). Marketing sets **no prices**.

## Open tasks

- [ ] Run trademark/domain/app-store/social checks on **Glasswing** (+ fallbacks) #task/marketing 🔺 📅 2026-08-22 ⛓ [[naming]]
- [ ] A/B the 3 alt hero headlines once the stats page is live #task/marketing 🔼 📅 2026-09-15 ⛓ [[lead-gen-plan]]
- [ ] Ship the "most/least reliable routes" PR data story for backlinks #task/marketing 🔼 📅 2026-09-30
- [ ] Confirm EU-vs-US launch market w/ [[sales]] (EU261 economics) #task/marketing 📅 2026-09-15
- [ ] Get [[staff-ml-engineer]] sign-off on public calibration claims before landing page ships #task/marketing 🔺 ⛓ [[staff-ml-engineer]] 📅 2026-09-15

## Sources

- All external claims cited in the linked notes (competitor/trademark, SEO volumes, disruption stats, B2B positioning) with access date 2026-08-08.
- Cross-refs: [[naming]], [[positioning]], [[messaging]], [[lead-gen-plan]], [[research-summary]], [[tier-matrix]], [[pricing-summary]], [[differentiation-thesis]], [[personas]]
