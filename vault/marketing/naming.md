---
type: marketing
title: Naming & Rename — Candidates + Recommendation
tags: [marketing, brand, naming]
status: draft
updated: 2026-08-08
---

# Naming & Rename

> "TravelPal" is a working name (see [[AGENTS]]). It reads generic, undifferentiated, and app-store-crowded — and it signals *companionship*, not *foresight/transparency*, which is our wedge ([[differentiation-thesis]], [[positioning]]). Recommend rename. All availability/trademark/app-store claims below are **checks to run — NOT verified**.

## Naming brief

The name must fit a **predictive, trustworthy, slightly nerdy** decision tool, and must carry our real wedge — **transparency + route-shopping + cheap-to-serve** — *not* accuracy (we will not out-predict Google/FlightAware Foresight, per [[differentiation-thesis]]). Avoid names that imply guaranteed accuracy or a "beat the model" claim (honesty rule, [[messaging]]). Should work for both B2C (P1/P2) and the B2B feed (P3/P4, the margin story in [[tier-matrix]]).

## Names to AVOID (collision found in research)

| Name | Why avoid | Source |
|------|-----------|--------|
| **Foresight** | FlightAware's ML product name **and** a FLYR, Inc. trademark for travel predictive-analytics API | measured (see Sources) |
| **Wingman** | Multiple live apps (paragliding tracker, airline social, dispatch system) | measured |
| **Skylark** | Skylark Travel Group holds a travel-software trademark | measured |
| **FlightCaster** | Dead YC 2009 startup, exact-JTBD baggage; may be free but confusing | measured |
| **FlyWise** | Existing app marketing "95% accuracy" — on-nose with the accuracy claim we explicitly reject | measured |

## Candidates

| # | Name | Rationale (ties to wedge) | Vibe | Risk |
|---|------|---------------------------|------|------|
| 1 | **Glasswing** ⭐ | *Glass* = glass-box (auditable) vs incumbents' black-box models → our transparency/calibration wedge for B2B ([[personas]] P3/P4); *wing* = aviation. A real transparent-winged butterfly → ready-made visual identity. Double meaning lands for both audiences. | Transparent, precise, quietly poetic-nerdy | Common English compound; must verify TM in software/travel classes |
| 2 | **Almanac** (or **Flight Almanac**) | Trusted-forecast heritage (Farmer's Almanac); route/carrier **base rates** = the historical spine + route-shopping cut. Signals honest, probabilistic, methodical. | Authoritative, nerdy, trustworthy | Generic word; likely needs a qualifier/compound for TM + domain |
| 3 | **Baserate** | Literal statistics term = calibrated, probabilistic, transparent. B2B insurers/TMCs immediately trust it. On-thesis for the feed. | Quant, honest, engineer-credible | May read dry/cold to P2 anxious flyers; coined-word TM likely cleaner |
| 4 | **Truebound** | *True* (calibrated/honest, not "accurate-hype") + *bound* (heading somewhere → travel). Coined → likely cleaner availability. | Trustworthy, directional, modern | Meaning less immediate; needs tagline support |
| 5 | **Telltale** | "Tells you before the airline does" — the exact JTBD in [[demand-evidence]]; an honest *tell*/signal. | Friendly, a little clever | "Telltale sign" can read mildly negative; Telltale Games TM in a different class (verify) |
| 6 | **Cleared** | "Cleared for takeoff" + *clarity/transparency*. Aviation-native, confident, short. | Confident, clean, aviation-insider | Very common word → hard exact-match domain/TM; verify |
| 7 | **Waypoint** | Aviation navigation term = a **decision point** on a route → route-shopping framing. | Navigational, practical | Heavily used SaaS/game name; TM crowding likely |

## Recommendation

- **Primary: `Glasswing`.** It is the only candidate whose core metaphor *is* the strategic wedge — glass-box transparency — and it reads as trustworthy/nerdy without implying accuracy superiority. It serves B2C ("clear, honest forecast") and B2B ("auditable, not a black box") from one word, and hands the design team a concrete visual system (transparent wing, layered/see-through UI) that satisfies [[brand-system]] and the non-template rule in `rules/web/design-quality.md`.
- **Fallback: `Truebound`** (cleanest likely availability as a coined word) or **`Almanac`**-based compound if a broader, warmer consumer tone is preferred.
- **Do not** ship a name implying guaranteed accuracy (rules out FlyWise-style framing).

## Checks to run BEFORE adopting any name (NONE verified here)

For the chosen name (run in this order; treat as blocking):

- [ ] **Trademark** — USPTO TESS + EUIPO search in classes **9** (software), **42** (SaaS), **39** (travel info). Screen for live marks & pending apps. #task/marketing 🔺 📅 2026-08-22
- [ ] **Domain** — `.com` first; acceptable fallbacks `.app` / `.ai` / `getX.com`. Check exact-match availability & squatter pricing. #task/marketing 🔺 📅 2026-08-22
- [ ] **App Store + Google Play** — search exact + near-duplicate names; check ranking crowding. #task/marketing 🔼 📅 2026-08-22
- [ ] **Social handles** — X, LinkedIn company page, Instagram, Reddit (for community, see [[lead-gen-plan]]). #task/marketing 🔽 📅 2026-08-22
- [ ] **Linguistic/negative-connotation** screen across EN + target EU launch markets ([[positioning]] leans EU). #task/marketing 📅 2026-08-22
- [ ] Route the finalist past legal/counsel before any public use. #task/marketing ⛓ [[positioning]]

## Handoff

- → [[brand-system]] / whoever builds the landing page: if `Glasswing` is chosen, the transparent-wing metaphor drives the visual direction.
- → [[positioning]], [[messaging]]: name choice must not undercut the "no accuracy claims" honesty rule.

## Sources

- [Foresight — FlightAware](https://www.flightaware.com/commercial/foresight/) · [FORESIGHT trademark (FLYR, Inc.) — Trademarkia](https://www.trademarkia.com/foresight-88029164) — accessed 2026-08-08 *(measured)*
- [Wingman paragliding app](https://www.wingmanfly.app/) · [Wingman social app — TIME](https://time.com/6157/wingman-app-airline-hookups/) — accessed 2026-08-08 *(measured)*
- [SKYLARK trademark — Skylark Travel Group, Justia](https://trademark.justia.com/owners/skylark-travel-group-inc-3141824) — accessed 2026-08-08 *(measured)*
- [FlightCaster — Y Combinator](https://www.ycombinator.com/companies/flightcaster) — accessed 2026-08-08 *(measured)*
- [FlyWise "95% accuracy" claim — Growth Market Reports](https://growthmarketreports.com/report/flight-delay-prediction-apps-market) — accessed 2026-08-08 *(report mill, low confidence)*
- Cross-refs: [[differentiation-thesis]], [[positioning]], [[personas]], [[tier-matrix]]
