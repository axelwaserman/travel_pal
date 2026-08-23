# TravelPal — Project Rules

## Pre-Code Gate (MANDATORY)

Before writing ANY code, you MUST ask the user about:
1. **Patterns** — architectural and design patterns to use
2. **Toolstack** — exact libraries, versions, and frameworks
3. **Implementation details** — specific decisions that affect code shape

Only proceed to writing-plans after explicit user approval of these choices.
This applies even when requirements seem obvious from the architecture doc.

## Tech Stack

- **Python**: 3.13 (`requires-python = ">=3.13"`); GIL-enabled. Free-threaded 3.13t was tried and dropped — Docker Hub has no 3.13t-slim and the test stack benefited none from it.
- **Data validation**: Pydantic v2 (all models; `BaseSettings` for config)
- **HTTP client**: pyreqwests (async-first; `ClientBuilder` + `basic_auth` for OpenSky)
- **Orchestrator**: Dagster (use `dagster:dagster-expert` + `dagster:dignified-python` skills)
- **Testing**: unit + integration + E2E required; pytest + pytest-asyncio; minimum 80% coverage
- **Type annotations**: full coverage, no `Any` without justification

## Skills to Use

Always invoke these skills for relevant tasks:
- `dagster:dagster-expert` — any Dagster asset, component, resource, sensor, schedule
- `dagster:dignified-python` — any Python code quality, typing, patterns
- `travelpal-pyreqwests` — HTTP client (OpenSkyAdapter, any external API call)
- `travelpal-pydantic-models` — config, API response models, validators
- `travelpal-dagster-resources` — ResourceParam, hardcoded_resource, Definitions wiring
- `travelpal-testing-layers` — test layer placement (unit / integration / E2E)
- `travelpal-opensky-adapter` — OpenSky endpoints, auth, chunking, limitations
- `travelpal-dbt-duckdb` — dbt models, NULL guards, DuckDB dialect
- `travelpal-seaweedfs` — S3/boto3 config, Parquet upload, moto mocking
- `travelpal-iceberg-nessie` — catalog init, schema definition, branch management
- `superpowers:writing-plans` — before implementing features
- `superpowers:brainstorming` — before writing-plans

## Conventions

- All Dagster resources use `ResourceParam[X]` type hints
- Pydantic models for all config and external API response shapes
- `_resources_or_empty()` pattern for unit-test-compatible `Definitions`
- dbt models: written directly in DuckDB dialect (single engine, Phase 0)
- No `cancellation_rate` — OpenSky only records completed flights (deferred to Phase 1)

## Responsive Design (MANDATORY)

Every UI change must be verified at both desktop (1280px+) and mobile (375px) before marking complete.

**Process:**
1. Design for mobile first — ensure key controls collapse or are accessible at 375px
2. Use `@media (max-width: 768px)` as the mobile breakpoint
3. Modal/panel overlays must have a visible dim backdrop at all viewports
4. Controls rows that overflow on mobile must be collapsible (toggle button pattern):
   - Button hidden on desktop (`display: none`), shown on mobile
   - Controlled panel hidden by default on mobile, toggled with `aria-expanded`
5. Test with Playwright at both viewports before closing the task

**Patterns in use:**
- `RoutePanel`: backdrop `<div>` with `onClick={onClose}` + dim overlay `rgba(0,0,0,0.4)` + `animation: backdrop-fade-in`
- `FlightLookup` controls: `lookup-controls-toggle` button (mobile) + `lookup-controls-row--open` modifier class

## End-to-End UAT (MANDATORY: do it yourself, do not hand off to user)

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
any MCP.

Only ask the user to test manually if:
- Visual judgment is required (typography polish, design feel)
- The bug only repros against external services the user controls (real OpenSky
  account, real BTS download)
- An explicit user gate (Pre-Code Gate, design approval) is in play
