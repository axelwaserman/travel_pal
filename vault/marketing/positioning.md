---
type: marketing
title: Positioning — Outcome-Led Wedge & Statement
tags: [marketing, brand, positioning]
status: draft
updated: 2026-08-10
---

# Positioning

> **Rev. per PR #13.** Pivot: lead on the **outcome/decision** ("we pick the flight that won't wreck your trip"), demote transparency to a supporting trust cue, and stop naming competitors defensively. **B2C-only** (B2B feed dropped). Working name **FlightPal** (see [[naming]]). Consumes [[personas]] (P1/P2 only), [[differentiation-thesis]], [[research-summary]].

## The single sharpest wedge (revised)

> **We don't just tell you *if* a flight is late — we pick the flight that won't wreck your trip.** FlightPal is a **flight-decision engine**: for a route, it ranks the options by how likely each is to actually get you there on time, on the aircraft you want, without blowing a connection. The lead is the **outcome** (the right pick), not the raw probability and not the method.

Why the shift: raw "will it be delayed?" is commoditized to $0 ([[research-summary]]). Users don't want a number — they want the *decision made for them*. So we sell the **best-pick recommendation**, and let reliability/aircraft/connection data be the engine underneath.

## One-line positioning statement

**For** travelers choosing or watching a flight, **FlightPal** finds and flags the **best flight for your route** — the option most likely to leave on time, on a good aircraft, with your connection intact — so you stop guessing and book with confidence.

## Claims guardrail (⚠️ FLAGGED — read before writing copy)

The review asked to claim we **"guarantee"** / **"ensure"** the **"best flight for your buck"** and that we are **"the only service"** that does so. Three of those words are a problem and I have **not** written them into copy — reasons, with honest alternatives:

| Requested word | Problem | Honest, still-strong alternative |
|----------------|---------|----------------------------------|
| **"guarantee" / "ensures"** | Output is probabilistic; an unqualified guarantee implies a remedy (refund) we haven't defined and creates ad-substantiation/legal exposure (FTC/EU). It also reopens the accuracy trap. | *"We find you the flight least likely to let you down."* Or define a **real, bounded service guarantee** (e.g. money-back on a paid tier if we failed to flag a delay we should have) — an honest promise we can keep. |
| **"for your buck"** | Implies **price/value** optimization. Our data spine is **on-time performance + weather/NOTAM — we ingest no fare data**, so we cannot substantiate a price claim. | *"the best flight for your trip"* / *"...for your day"* — a reliability/experience claim we can back. |
| **"the only service"** | Superiority/uniqueness claim — false (Google, Flighty, etc. overlap) and requires proof. | *"the simplest way to pick the flight that won't wreck your trip."* |

**Net:** I actioned the *direction* (outcome-led, confident, decision-first) but flagged the literal wording. See my note to [[AGENTS]]/team-lead. If the human still wants a hard guarantee, we should scope a **defined service-level guarantee** with legal, not an open-ended one.

## What we say instead of naming competitors

Per the review, drop the defensive competitor grid — most users don't know Cirium/Foresight. Lead with the user's own problem and our pick:

- *"You already know a quarter of flights run late. FlightPal tells you which of your options won't."*
- Category claim (honest, ownable): **"the flight-picking assistant that reads the reliability data so you don't have to."**

*(Internal-only note: our real edge vs incumbents is still route-shopping + aircraft/connection intelligence packaged as a decision — but that is a strategy note, not user-facing copy.)*

## Positioning grid (internal strategy only — not for landing copy)

- **X — Tracks one flight ↔ Picks the best of your options**
- **Y — Raw number ↔ Made decision**

FlightPal targets the top-right (**picks best option × makes the decision**): Google/Flighty sit left (track/track+number). This is the whitespace, but we express it to users as *outcome*, not as a competitor teardown.

## Honesty guardrails (still binding)

- Probabilistic, calibrated language under the hood; **no fabricated accuracy %**; never repeat the debunked "89.3%/MIT/7.2B" Google stats ([[research-summary]]).
- Confidence/uncertainty stays visible where it aids the decision (a "we're less sure here" cue), but it is **not** the headline anymore.
- Any "guarantee" must be a **defined, bounded** promise (see guardrail table), never open-ended.

## Handoff

- → [[messaging]]: outcome-led value props + connection-miss + aircraft/cabin angle; drop B2B personas.
- → [[lead-gen-plan]]: the funnel sells the *pick*, not the *method*.
- → [[staff-ml-engineer]]: confirm the ranking/"best pick" logic is defensible and that connection-miss + aircraft-assignment signals are feasible from the forward-ingestion spine.

## Sources

- Commoditization + demand framing: [[research-summary]], [[demand-evidence]] (primary URLs there) — accessed 2026-08-10.
- [Best flight tracker apps 2026 — Blacklane](https://www.blacklane.com/en/blog/travel/airports/the-best-mobile-flight-tracker-apps/) — accessed 2026-08-10 *(measured, category framing)*.
