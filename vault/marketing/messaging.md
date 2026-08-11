---
type: marketing
title: Messaging — Value Props, Landing Copy
tags: [marketing, brand, messaging, copy]
status: draft
updated: 2026-08-10
---

# Messaging

> **Rev. per PR #13.** Outcome-led ([[positioning]]), **B2C-only** (B2B personas dropped), working name **FlightPal** ([[naming]]). New angles: **connection-miss risk** and **aircraft/cabin quality**. Tiers referenced **by name only — prices owned by [[sales]]**. Honesty guardrail: see [[positioning]] "Claims guardrail" (no open-ended guarantee, no "for your buck").

## Message architecture

- **Category:** flight-decision assistant (picks the best flight for your route) — not "another delay tracker."
- **Core promise:** *Pick the flight that won't wreck your trip.*
- **Proof pillars:** (1) **Reliability** — which option actually leaves on time; (2) **Connection-safe** — won't strand you between legs; (3) **Right aircraft** — the cabin you actually want.
- **Never:** open-ended guarantees, "best for your buck" (no fare data), "only service," invented accuracy stats.

## Value props by persona (B2C only)

| Persona ([[personas]]) | Their pain (real user language, [[demand-evidence]]) | FlightPal value prop | Tier fit ([[tier-matrix]]) |
|------------------------|------------------------------------------------------|----------------------|----------------------------|
| **P1 Optimizing Nomad** | *"Airlines know your flight will be delayed long before they tell you."* | Rank your route's options by real reliability + aircraft + connection safety; get an explained heads-up in time to rebook | **Plus** → **Pro** |
| **P2 Anxious Occasional** | *"Just tell me plainly which flight to pick — and if I should worry."* | One clear recommendation per route, in plain language, with a worry-or-not read — free (limited mode) | **Free** (→ insurance/rebook handoff) |

## New messaging angles (per review)

### 1. Connection-miss risk (messaging:20)
Most tools score each leg alone. FlightPal scores the **itinerary**: leg 1 often runs late while leg 2 leaves on time → a hidden misconnect. Copy:
> *"Your first leg is the risk. FlightPal checks whether it'll still make your connection — before you book the tight one."*

### 2. Aircraft / cabin quality via tail assignment (lead-gen:28)
Users care which **specific aircraft (tail)** is assigned — was the cabin recently refurbished, is it the narrow-body or the nicer wide-body? Forward daily ingestion lets us track the planned tail. Copy:
> *"Same route, very different plane. FlightPal flags the aircraft you're actually on — old cabin or fresh refit."*
> *(Honest scope: aircraft **assignments can change** close to departure — we show the current plan, not a promise.)*

## Value props by tier (benefit-led, no prices)

- **Free (limited mode, 5 searches/day)** — *"Pick smarter on your next flight — free."* A best-flight recommendation for a route, reliability + aircraft basics.
- **Plus** — *"Told before the airline tells you."* Proactive delay + misconnect alerts on watched flights, full route + aircraft analytics.
- **Pro** — *"For people who live in airports."* Unlimited watchlist, full history, multi-leg itinerary risk.

## Landing page — hero

**Headline:**
> **Pick the flight that won't wreck your trip.**

**Subhead:**
> FlightPal reads a decade of on-time data, live conditions, connection risk, and which aircraft you'll actually fly — then tells you the best option for your route.

**Three supporting benefit lines:**
1. **The best pick, not just a number.** We rank your route's flights by how likely each is to get you there on time.
2. **Won't strand you.** We check whether a tight connection actually holds before you book it.
3. **Know your plane.** See which aircraft is assigned — fresh cabin or tired old bird.

**Primary CTA:** `Find my best flight — free` → **Secondary:** `Get delay & misconnect alerts` (→ Plus)

### Honesty microcopy (ship alongside any recommendation)
- *"Our best read, not a promise — conditions and aircraft can change; airlines make the final call."*
- *"Based on historical performance + current conditions."*

## Alt headlines (for A/B — [[lead-gen-plan]])

1. *"Which flight won't ruin your day?"* (P1/P2 problem-lead)
2. *"Stop guessing which flight to book."* (decision-lead)
3. *"The smart way to pick a flight."* (simplicity-lead)

## Tone rules

- Plain over clever; specific over hype. Lead with the pick; keep the "why" one tap away.
- Confident about the **recommendation**, honest about **certainty** (things change; we show current best).

## Handoff

- → [[brand-system]]: headline/tone feed the visual + voice system.
- → [[lead-gen-plan]]: hero + alt headlines are the A/B inputs; benefit lines seed the Chrome-extension + SEO copy.
- → [[staff-ml-engineer]]: confirm connection-miss scoring + tail-assignment tracking are feasible from forward ingestion, and that "best pick" ranking is defensible.

## Sources

- User-language quotes from [[demand-evidence]] (primary URLs there): [Tom's Guide](https://tomsguide.com/computing/software/this-travel-app-can-now-predict-delays-for-your-next-flight-via-ai), [View From The Wing](https://viewfromthewing.com/how-to-predict-your-flight-will-be-delayed-and-get-a-leg-up-rebooking-travel/) — accessed 2026-08-10
- Disruption stats ([[demand-evidence]]): [thetraveler.org](https://www.thetraveler.org/half-of-airline-passengers-still-face-disruptions-in-2025/) — accessed 2026-08-10 *(estimated)*
- Cross-refs: [[positioning]], [[personas]], [[tier-matrix]], [[naming]]
