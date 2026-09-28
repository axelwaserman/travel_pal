---
type: charter
title: AGENTS — TravelPal Product Team
tags: [agents, charter, moc]
status: draft
updated: 2026-08-23
---

# AGENTS — TravelPal Product Team

> **Working name:** TravelPal (rename is an open question — see [[marketing]]).
> **What we are building:** a product that **predicts whether a flight will be delayed and by how long**, using an ML model served over an Apache Iceberg lakehouse queried through DuckDB, with fresher context (weather, news/NOTAMs) joined at serve time.

This file is the **map of content (MOC)** and operating contract for the multi-agent product team. Open the **repository root as your Obsidian vault** so the wikilinks below resolve.

---

## Code rules (governs all code)

> Migrated from the former `CLAUDE.md` (2026-08-23). The Pre-Code Gate and tech stack below are binding.

### Pre-Code Gate (MANDATORY)

Before writing ANY code, you MUST ask the user about:
1. **Patterns** — architectural and design patterns to use
2. **Toolstack** — exact libraries, versions, and frameworks
3. **Implementation details** — specific decisions that affect code shape

Only proceed to writing-plans after explicit user approval of these choices.
This applies even when requirements seem obvious from the architecture doc.

### Tech Stack

- **Python**: 3.14 (`requires-python = ">=3.14"`); GIL-enabled.
- **Data validation**: Pydantic v2 (all models; `BaseSettings` for config)
- **HTTP client**: pyreqwests (async-first; `ClientBuilder` + `basic_auth` for OpenSky)
- **Orchestrator**: Dagster (use `dagster-expert` + `dignified-python` skills)
- **Testing**: unit + integration + E2E required; pytest + pytest-asyncio; minimum 80% coverage
- **Type annotations**: full coverage, no `Any` without justification

### Skills to Use

Always invoke these skills for relevant tasks (via the `skill` tool, name-only):
- `dagster-expert` — any Dagster asset, component, resource, sensor, schedule
- `dignified-python` — any Python code quality, typing, patterns
- `travelpal-pyreqwests` — HTTP client (OpenSkyAdapter, any external API call)
- `travelpal-pydantic-models` — config, API response models, validators
- `travelpal-dagster-resources` — ResourceParam, hardcoded_resource, Definitions wiring
- `travelpal-testing-layers` — test layer placement (unit / integration / E2E)
- `travelpal-opensky-adapter` — OpenSky endpoints, auth, chunking, limitations
- `travelpal-dbt-duckdb` — dbt models, NULL guards, DuckDB dialect
- `travelpal-seaweedfs` — S3/boto3 config, Parquet upload, moto mocking
- `travelpal-iceberg-nessie` — catalog init, schema definition, branch management

### Conventions

- All Dagster resources use `ResourceParam[X]` type hints
- Pydantic models for all config and external API response shapes
- `_resources_or_empty()` pattern for unit-test-compatible `Definitions`
- dbt models: written directly in DuckDB dialect (single engine, Phase 0)
- No `cancellation_rate` — OpenSky only records completed flights (deferred to Phase 1)

### End-to-End UAT (MANDATORY: do it yourself, do not hand off to user)

When the user asks "did you test it" or "does it work" — actually run the full
stack and verify, do not just describe steps. The repo has Playwright +
DuckDB-WASM + Dagster wired up; you have everything needed.

Steps:
1. `just down -v` → `just up` → `just buckets-init` (clean SeaweedFS state)
2. `just run-pipeline` (materializes bts_on_time partition + raw + transformed + frontend_exports)
3. `just ls-exports` — confirm 5 parquets in `frontend-exports`
4. `cd frontend && npm run dev &` (vite at :5173) — or `npm run preview` after `npm run build`
5. Run Playwright headed against the running dev server:
   `cd frontend && npx playwright test --reporter=list`
   Screenshots + traces land in `frontend/test-results/` and `frontend/playwright-report/`
6. For ad-hoc DOM inspection beyond the smoke spec, write a one-off Playwright
   script (or extend `tests/e2e/smoke.spec.ts`) that calls `page.screenshot`,
   `page.locator(...).innerHTML()`, and `page.evaluate(() => document.title)`.

If a chrome-devtools or playwright MCP is attached, prefer that for interactive
inspection. Otherwise the local `npx playwright` path works headlessly without
any MCP. (Note: no playwright/chrome-devtools MCP is configured in opencode yet.)

Only ask the user to test manually if:
- Visual judgment is required (typography polish, design feel)
- The bug only repros against external services the user controls (real OpenSky
  account, real BTS download)
- An explicit user gate (Pre-Code Gate, design approval) is in play

---

## 1. How this relates to existing docs

- **Code rules** live in the "Code rules" section above: the Pre-Code Gate, tech stack, and the `travelpal-*` skills. Before any agent's recommendation turns into code, the Pre-Code Gate applies.
- **`tech_product_Architecture.txt`** is the legacy architecture reference; the vault notes supersede it in places (see `vault/engineering/architecture-summary.md`).
- **This vault** is the new home for product strategy, research, and cross-functional planning. Engineering/ML deep-dives link back to the code.

## 2. Product reframe (why the team exists)

The legacy architecture (`tech_product_Architecture.txt`) framed TravelPal as a **descriptive** "analyze your past travel" timeliness explorer. We are pivoting to a **predictive** product:

- **Core prediction:** for a given flight / route / time, output `P(delayed)` and an expected/qualified **delay-minutes** estimate with a calibrated uncertainty band.
- **Data spine:** historical flight performance in **Iceberg** (Nessie catalog, SeaweedFS storage), transformed with **dbt + DuckDB**, plus **fresher signals** (weather, news/NOTAMs) joined near serve time.
- **Serving:** a **FastAPI** backend loads a pretrained model; **Dagster** orchestrates backfills, feature builds, training, and batch scoring; **React + DuckDB-WASM** frontend serves cheap descriptive analytics at the edge and calls the API for live predictions.

The team's job is to make this a *product*, not just a pipeline: real user demand, a pricing model, a brand, and an implementable product + ML architecture.

## 3. The team

| Agent | Mandate | Prompt |
|-------|---------|--------|
| Product Researcher | Existing solutions on the web + real user demand, personas, JTBD, gaps | [[product-researcher]] |
| Sales | Pricing model — free-tier query caps, paid tiers, unit economics | [[sales]] |
| Marketing | Brand + possible rename, positioning, lead generation | [[marketing]] |
| Staff Product Engineer | Ingestion/backfill, Iceberg↔DuckDB, batch vs fresh data, frontend-vs-backend data split, product shape per pricing tier | [[staff-product-engineer]] |
| Staff ML Engineer | Model family selection, training orchestration from Dagster, deployment/serving | [[staff-ml-engineer]] |
| Security Engineer | Threat-model the product-engineering design: data exposure, multi-tenant isolation, abuse/cost attacks, privacy/GDPR | [[security-engineer]] |
| Staff Platform Engineer | Low-maintenance hosting for frontend + backend + DuckDB compute + ETL + event bus; hosting split with product eng | [[staff-platform-engineer]] |

## 4. Dependency & handoff order

```
product-researcher ──► sales ──► marketing
        │                │
        └────────────────┴──► staff-product-engineer ──► staff-ml-engineer
                                       │
                                       ├──► security-engineer  ────┐
                                       └──► staff-platform-engineer ┘  (security ↔ platform sync)
```

- **Research first.** Demand + competitor gaps ground every downstream decision.
- **Sales** consumes research to set pricing; **marketing** consumes both to set brand + GTM.
- **Product engineering** consumes the pricing model (it dictates what compute/data is free vs paid) and produces the product/data architecture.
- **ML engineering** consumes the feature/serving contract from product engineering.
- **Security engineering** threat-models the product-engineering (and platform) design; its CRITICAL/HIGH controls are binding requirements that feed back into both.
- **Platform engineering** consumes the product architecture to place each component on the lowest-ops host; syncs bidirectionally with product eng (DuckDB/ETL/event-bus hosting) and security (isolation/secrets).

Agents may run in parallel where inputs already exist, but each must **cite the upstream note it relied on** (wikilink) and flag when it is assuming an input that is not yet written.

## 5. Vault conventions (Obsidian)

- **Wikilinks** for every cross-reference: `[[note-name]]`. Link liberally; a link to a not-yet-written note is a valid TODO marker.
- **Frontmatter** on every note: `type`, `title`, `tags`, `status` (`draft` | `review` | `approved`), `updated` (absolute date).
- **One concern per note.** Prefer many small linked notes over one large file (mirrors the repo's file-organization rule).
- **Folder layout** (created lazily as content lands; only `agents/` exists now):
  - `vault/agents/` — these agent system-prompt notes
  - `vault/product/` — research, personas, competitor teardowns, PRDs
  - `vault/sales/` — pricing model, tier matrix, unit economics
  - `vault/marketing/` — brand, positioning, GTM, landing copy
  - `vault/engineering/` — product architecture, data flow, ingestion design
  - `vault/ml/` — model selection, training/serving design, evaluation
  - `vault/security/` — threat model, access control, abuse/cost, privacy
  - `vault/platform/` — hosting options, cost model, orchestration/storage, event bus
- **Sources are mandatory** for any external claim (competitor pricing, market size, user quotes): include a `## Sources` section with URLs and access date. No fabricated numbers — if unknown, say "unknown" and note how to find it.

## 6. Task tracking — Obsidian-native (Tasks + Dataview)

We track work as **checkbox tasks inside vault notes**, queried with Dataview. No external service.

**Task line format** (Tasks plugin emoji syntax):

```markdown
- [ ] Draft competitor teardown for Hopper #task/product 🔺 📅 2026-08-15
- [ ] Define free-tier daily query cap #task/sales 🔼 📅 2026-08-18
```

Conventions:
- Every task carries exactly one owner tag: `#task/product`, `#task/sales`, `#task/marketing`, `#task/eng`, `#task/ml`, `#task/security`, `#task/platform`.
- Priority via Tasks emoji: 🔺 highest, 🔼 high, (none) normal, 🔽 low.
- Due date via `📅 YYYY-MM-DD` (absolute — never "next week").
- Cross-agent dependencies: append `⛓ [[blocking-note]]` and mention the blocker in prose.

**Roll-up dashboard** — put this Dataview block in a `vault/tasks.md` note (create when the first tasks exist):

````markdown
```dataview
TASK
WHERE !completed AND contains(tags, "#task")
GROUP BY filter(tags, (t) => startswith(t, "#task/"))[0] AS "Owner"
SORT priority DESC
```
````

> If you later prefer Todoist over Obsidian-native tasks, the owner tags map 1:1 to Todoist labels — swap the sink, keep the taxonomy.

## 7. Shared operating rules for every agent

1. **Read before you write.** Load `AGENTS.md` (code rules included), `tech_product_Architecture.txt`, and your upstream agents' notes first.
2. **Evidence over assertion.** Cite sources; distinguish *measured*, *estimated*, and *assumed*. Never invent metrics, quotes, or competitor prices.
3. **Respect locked tech decisions** in the Code rules section (Python 3.14, Pydantic v2, Dagster, dbt+DuckDB, Iceberg/Nessie, SeaweedFS, React/DuckDB-WASM). Propose changes explicitly with rationale; do not silently assume a different stack. FastAPI (backend) and the ML library are *open* additions to be justified.
4. **Stay in your lane, name your handoffs.** Produce your artifact, then list what the next agent needs from you and what you need from them (wikilinks).
5. **Draft status by default.** New notes are `status: draft`. Only the human moves a note to `approved`.
6. **No code without the gate.** Recommendations are fine; implementation waits for the Pre-Code Gate (Code rules section) and explicit human approval.
7. **Terse, structured, skimmable.** Tables, bullets, short sections. This is a review artifact, not an essay.

---

## Review checklist (for the human)

- [ ] Team roster + mandates match intent
- [ ] Reframe (predictive product) is correct
- [ ] Vault conventions + task workflow acceptable
- [ ] Each agent prompt is scoped right — see the five notes in `vault/agents/`
