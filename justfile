# TravelPal — local dev / UAT commands
# Run `just` (no args) to list recipes.

set dotenv-load := true
set positional-arguments := true

PIPELINE_DIR := "pipeline"
FRONTEND_DIR := "frontend"
COMPOSE_PROJECT := "travel_pal"

# Default: list recipes
default:
    @just --list

# ─────────────── Stack lifecycle ───────────────

# Build images + start every service (infra + dagster app). Idempotent.
up:
    docker compose --profile app up -d --build
    @echo "Waiting for services to become healthy..."
    @just _wait-healthy
    @just init-buckets
    @echo ""
    @echo "Stack up. Dagster UI: http://localhost:3000"
    @echo "Run 'just materialize' next."

# Start infra only (no dagster app — useful when running pytest against live infra).
up-infra:
    docker compose up -d postgres nessie seaweedfs-master seaweedfs-volume seaweedfs-filer seaweedfs-s3
    @just _wait-healthy
    @just init-buckets

# Stop and remove all containers (volumes preserved).
down:
    docker compose --profile app down

# Stop + wipe volumes. DESTRUCTIVE — postgres, nessie state, parquet files all gone.
nuke:
    docker compose --profile app down -v

# Block until every running compose service reports healthy.
_wait-healthy:
    #!/usr/bin/env bash
    set -euo pipefail
    for i in $(seq 1 60); do
      unhealthy=$(docker compose ps --format json | jq -r 'select(.Health != "" and .Health != "healthy") | .Name' || true)
      if [ -z "$unhealthy" ]; then
        echo "All services healthy."
        exit 0
      fi
      echo "Waiting on: $unhealthy"
      sleep 2
    done
    echo "Timed out waiting for healthy services." >&2
    docker compose ps
    exit 1

# Compose service status.
ps:
    docker compose ps

# Tail logs (all services or one). Usage: just logs            |  just logs dagster-webserver
logs *service:
    docker compose logs -f {{service}}

# ─────────────── SeaweedFS / S3 ───────────────

# Idempotently create raw-flights + frontend-exports buckets and configure access.
init-buckets:
    docker compose cp scripts/seaweedfs/init.sh seaweedfs-master:/tmp/init.sh
    docker compose exec -T seaweedfs-master sh /tmp/init.sh

# List frontend-export parquet for current AIRPORT_ICAO (default KJFK).
ls-exports airport="KJFK":
    AWS_ACCESS_KEY_ID=admin AWS_SECRET_ACCESS_KEY=admin \
      aws s3 ls s3://frontend-exports/{{airport}}/ --endpoint-url http://localhost:8333

# List raw flights bucket.
ls-raw:
    AWS_ACCESS_KEY_ID=admin AWS_SECRET_ACCESS_KEY=admin \
      aws s3 ls s3://raw-flights/ --recursive --endpoint-url http://localhost:8333

# ─────────────── Dagster materialization ───────────────

# Materialize the monthly-partitioned bts_on_time asset for a given partition.
# Partition keys are ISO date strings anchored at month-start (YYYY-MM-01).
# Usage: just materialize-bts                 # defaults to 2024-01-01
#        just materialize-bts 2024-02-01      # any month
materialize-bts partition="2024-01-01":
    docker compose exec dagster-webserver dagster asset materialize \
      --select bts_on_time --partition "{{partition}}" -m pipeline

# Materialize a single asset or asset selection inside the dagster-webserver container.
# Selections are comma-separated. Use '+' suffix for downstream graph traversal.
# Includes the 2024-01-01 bts_on_time partition first so transformed_flights
# (which depends on it via AssetIn) has its upstream populated.
# Usage: just materialize                     # full default selection
#        just materialize raw_flights         # subset
#        just materialize "raw_flights,transformed_flights"
materialize selection="raw_flights,transformed_flights,frontend_exports": materialize-bts
    docker compose exec dagster-webserver dagster asset materialize \
      --select "{{selection}}" -m pipeline

# Full pipeline materialize end-to-end (bts → raw → transformed → exports).
run-pipeline: (materialize "raw_flights,transformed_flights,frontend_exports")

# Open the Dagster UI in default browser (mac).
ui:
    open http://localhost:3000

# Open SeaweedFS filer UI (browse parquet files at /buckets/<bucket>/).
ui-files:
    open http://localhost:8888/buckets/

# Open SeaweedFS master UI (cluster topology + volumes).
ui-master:
    open http://localhost:9333

# Open Nessie catalog UI.
ui-nessie:
    open http://localhost:19120

# ─────────────── Tests ───────────────

# Run all backend tests (pytest).
test-backend:
    cd {{PIPELINE_DIR}} && uv run pytest -q

# Backend tests with coverage report.
test-backend-cov:
    cd {{PIPELINE_DIR}} && uv run pytest --cov=pipeline --cov-report=term-missing

# Single backend test file or node id.
# Usage: just test-backend-one tests/test_asset_transformed_flights.py
test-backend-one target:
    cd {{PIPELINE_DIR}} && uv run pytest -v {{target}}

# Run frontend unit tests (vitest).
test-frontend:
    cd {{FRONTEND_DIR}} && npm run test:unit

# Run frontend E2E (Playwright). Requires `just frontend-dev` running OR --webServer in playwright config.
test-e2e:
    cd {{FRONTEND_DIR}} && npm run test:e2e

# Everything: backend + frontend unit. (E2E excluded — needs running stack.)
test: test-backend test-frontend

# ─────────────── Frontend dev ───────────────

# Vite dev server — http://localhost:5173
frontend-dev:
    cd {{FRONTEND_DIR}} && npm run dev

# Production build (typecheck + bundle).
frontend-build:
    cd {{FRONTEND_DIR}} && npm run build

# Lint frontend.
frontend-lint:
    cd {{FRONTEND_DIR}} && npm run lint

# ─────────────── End-to-end UAT ───────────────

# Bring everything up + materialize + show export listing. Doesn't start vite (run `just frontend-dev` separately).
uat: up materialize ls-exports
    @echo ""
    @echo "Pipeline materialized. Start frontend with: just frontend-dev"

# Smoke: verify exports landed for AIRPORT_ICAO.
verify-exports airport="KJFK":
    @just ls-exports {{airport}} | grep -E "route_timeliness.parquet|daily_timeliness.parquet"

# ─────────────── Misc ───────────────

# Open a shell inside the dagster-webserver container.
shell-dagster:
    docker compose exec dagster-webserver bash

# Open a postgres psql session.
psql:
    docker compose exec postgres psql -U dagster -d dagster

# Tail dagster-webserver logs only (most useful during materialize).
logs-dagster:
    docker compose logs -f dagster-webserver

# Clean local pytest/coverage artifacts.
clean:
    rm -rf {{PIPELINE_DIR}}/.coverage {{PIPELINE_DIR}}/.pytest_cache {{PIPELINE_DIR}}/build
    find {{PIPELINE_DIR}} -name __pycache__ -type d -prune -exec rm -rf {} +
