# TravelPal — Project Rules

## Pre-Code Gate (MANDATORY)

Before writing ANY code, you MUST ask the user about:
1. **Patterns** — architectural and design patterns to use
2. **Toolstack** — exact libraries, versions, and frameworks
3. **Implementation details** — specific decisions that affect code shape

Only proceed to writing-plans after explicit user approval of these choices.
This applies even when requirements seem obvious from the architecture doc.

## Tech Stack

- **Python**: 3.13t (free-threaded; `python3.13t` interpreter, `requires-python = ">=3.13"`)
- **Data validation**: Pydantic v2 (all models; `BaseSettings` for config)
- **HTTP client**: pyreqwests (async-first; `ClientBuilder` + `basic_auth` for OpenSky)
- **Orchestrator**: Dagster (use `dagster:dagster-expert` + `dagster:dignified-python` skills)
- **Testing**: unit + integration + E2E required; pytest + pytest-asyncio; minimum 80% coverage
- **Type annotations**: full coverage, no `Any` without justification

## Skills to Use

Always invoke these skills for relevant tasks:
- `dagster:dagster-expert` — any Dagster asset, component, resource, sensor, schedule
- `dagster:dignified-python` — any Python code quality, typing, patterns
- `travelpal-python-3.13t` — free-threading, `type` aliases, 3.13-specific patterns
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
