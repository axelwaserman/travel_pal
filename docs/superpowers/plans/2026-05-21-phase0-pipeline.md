# TravelPal Phase 0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete data pipeline from OpenSky historical flight data through an Iceberg lakehouse to a DuckDB-WASM browser frontend for a single airport (JFK).

**Architecture:** Dagster Python assets pull bulk Parquet from OpenSky, write raw Iceberg tables to SeaweedFS via PyIceberg/Nessie, dbt-duckdb transforms them into aggregates, and a final asset exports query-ready Parquet to a public SeaweedFS bucket prefix that DuckDB-WASM queries directly in the browser.

**Tech Stack:** Python 3.12, Dagster 1.x, PyIceberg, DuckDB ≥ 1.4.0, dbt-duckdb, sqlglot, SeaweedFS, Project Nessie, PostgreSQL (Dagster storage), React 18, Vite, @duckdb/duckdb-wasm

---

## File Map

```
travel_pal/
├── docker-compose.yml                         # All 6 infra services
├── .env.example                               # Environment variable template
│
├── pipeline/                                  # Dagster project root
│   ├── pyproject.toml                         # Python deps + dagster config
│   ├── pipeline/
│   │   ├── __init__.py                        # Dagster Definitions entry point
│   │   ├── assets/
│   │   │   ├── __init__.py
│   │   │   ├── raw_flights.py                 # Asset: fetch OpenSky → SeaweedFS + Nessie
│   │   │   ├── transformed_flights.py         # Asset: dbt-duckdb execution
│   │   │   └── frontend_exports.py            # Asset: export Parquet slices for browser
│   │   ├── resources/
│   │   │   ├── __init__.py
│   │   │   ├── seaweedfs.py                   # SeaweedFS S3 client resource
│   │   │   ├── nessie.py                      # PyIceberg + Nessie catalog resource
│   │   │   └── opensky.py                     # OpenSky source adapter (thin interface)
│   │   └── config.py                          # Typed config: airport ICAO, date range, URLs
│   │
│   └── transforms/                            # dbt project
│       ├── dbt_project.yml
│       ├── profiles.yml                       # dbt-duckdb profile pointing at Iceberg
│       ├── models/
│       │   ├── staging/
│       │   │   └── stg_flights.sql            # ANSI SQL: cast + clean raw OpenSky fields
│       │   ├── intermediate/
│       │   │   └── fct_flight_performance.sql # ANSI SQL: delay mins, on-time flag, cancelled
│       │   └── marts/
│       │       ├── agg_route_timeliness.sql   # ANSI SQL: per-route metrics
│       │       └── agg_daily_timeliness.sql   # ANSI SQL: per-day metrics
│       └── tests/
│           ├── stg_flights_not_null.yml       # dbt schema tests
│           └── agg_route_timeliness_values.yml
│
├── transpiler/                                # sqlglot build-time transpilation
│   ├── transpile.py                           # Reads ANSI SQL models → emits DuckDB SQL
│   └── tests/
│       └── test_transpile.py
│
└── frontend/                                  # React + Vite app
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── db/
    │   │   ├── client.ts                      # DuckDB-WASM init + singleton
    │   │   └── queries.ts                     # Typed query functions (flight lookup, timeliness)
    │   ├── sql/                               # Pre-compiled DuckDB SQL (output of transpiler)
    │   │   ├── flight_lookup.sql
    │   │   └── daily_timeliness.sql
    │   └── components/
    │       ├── FlightLookup/
    │       │   ├── FlightLookup.tsx           # F1.1: query box + results card
    │       │   └── FlightLookup.css
    │       └── TimelinessDashboard/
    │           ├── TimelinessDashboard.tsx    # F1.2: metrics panels
    │           └── TimelinessDashboard.css
    └── public/
        └── sql/                               # Vite copies transpiled SQL here at build time
```

---

## Task 1: Docker Compose infrastructure

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: dagster
      POSTGRES_PASSWORD: dagster
      POSTGRES_DB: dagster
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dagster"]
      interval: 5s
      timeout: 5s
      retries: 5

  nessie:
    image: projectnessie/nessie:0.91.3
    ports:
      - "19120:19120"
    environment:
      QUARKUS_DATASOURCE_JDBC_URL: "jdbc:postgresql://postgres:5432/dagster"
      QUARKUS_DATASOURCE_USERNAME: dagster
      QUARKUS_DATASOURCE_PASSWORD: dagster
      NESSIE_VERSION_STORE_TYPE: JDBC
    depends_on:
      postgres:
        condition: service_healthy

  seaweedfs-master:
    image: chrislusf/seaweedfs:3.68
    command: master -ip=seaweedfs-master -port=9333
    ports:
      - "9333:9333"

  seaweedfs-volume:
    image: chrislusf/seaweedfs:3.68
    command: volume -mserver=seaweedfs-master:9333 -port=8080 -s3.port=8333
    ports:
      - "8080:8080"
      - "8333:8333"
    depends_on:
      - seaweedfs-master

  dagster-webserver:
    build:
      context: ./pipeline
      dockerfile: Dockerfile
    command: dagster-webserver -h 0.0.0.0 -p 3000
    ports:
      - "3000:3000"
    environment:
      DAGSTER_POSTGRES_USER: dagster
      DAGSTER_POSTGRES_PASSWORD: dagster
      DAGSTER_POSTGRES_DB: dagster
      DAGSTER_POSTGRES_HOST: postgres
      SEAWEEDFS_S3_ENDPOINT: http://seaweedfs-volume:8333
      SEAWEEDFS_ACCESS_KEY: ${SEAWEEDFS_ACCESS_KEY}
      SEAWEEDFS_SECRET_KEY: ${SEAWEEDFS_SECRET_KEY}
      NESSIE_ENDPOINT: http://nessie:19120/api/v1
      AIRPORT_ICAO: KJFK
      INGEST_START_DATE: "2024-01-01"
      INGEST_END_DATE: "2024-12-31"
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./pipeline:/opt/dagster/app

  dagster-daemon:
    build:
      context: ./pipeline
      dockerfile: Dockerfile
    command: dagster-daemon run
    environment:
      DAGSTER_POSTGRES_USER: dagster
      DAGSTER_POSTGRES_PASSWORD: dagster
      DAGSTER_POSTGRES_DB: dagster
      DAGSTER_POSTGRES_HOST: postgres
      SEAWEEDFS_S3_ENDPOINT: http://seaweedfs-volume:8333
      SEAWEEDFS_ACCESS_KEY: ${SEAWEEDFS_ACCESS_KEY}
      SEAWEEDFS_SECRET_KEY: ${SEAWEEDFS_SECRET_KEY}
      NESSIE_ENDPOINT: http://nessie:19120/api/v1
      AIRPORT_ICAO: KJFK
      INGEST_START_DATE: "2024-01-01"
      INGEST_END_DATE: "2024-12-31"
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./pipeline:/opt/dagster/app

volumes:
  postgres_data:
```

- [ ] **Step 2: Write `.env.example`**

```bash
# SeaweedFS S3 credentials (set via `weed shell` after first run)
SEAWEEDFS_ACCESS_KEY=admin
SEAWEEDFS_SECRET_KEY=admin

# Copy to .env and fill in before running docker compose up
```

- [ ] **Step 3: Verify services start**

```bash
cp .env.example .env
docker compose up -d postgres nessie seaweedfs-master seaweedfs-volume
docker compose ps
```

Expected: all four services show `running` or `healthy` within 30 seconds.

- [ ] **Step 4: Verify Nessie is reachable**

```bash
curl http://localhost:19120/api/v1/config
```

Expected: JSON response with `"defaultBranch":"main"`.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "chore: add docker compose infra (postgres, nessie, seaweedfs, dagster)"
```

---

## Task 2: SeaweedFS S3 bucket setup

**Files:**
- No new files — bucket configured via SeaweedFS CLI

- [ ] **Step 1: Create the S3 buckets**

```bash
# Connect to SeaweedFS master shell
docker compose exec seaweedfs-master weed shell -master=localhost:9333
```

Inside the shell:
```
s3.bucket.create -name raw-flights
s3.bucket.create -name frontend-exports
s3.configure -access_key=admin -secret_key=admin -actions=Read,Write,List,Tagging -apply
```

- [ ] **Step 2: Set frontend-exports bucket to public read**

Still inside weed shell:
```
s3.configure -buckets=frontend-exports -access_key="" -secret_key="" -actions=Read,List -apply
```

Exit with `Ctrl+D`.

- [ ] **Step 3: Verify S3 API works**

```bash
AWS_ACCESS_KEY_ID=admin AWS_SECRET_ACCESS_KEY=admin \
  aws s3 ls s3://raw-flights --endpoint-url http://localhost:8333
```

Expected: empty listing, no error.

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "chore: document seaweedfs bucket setup steps in .env.example"
```

Add to `.env.example`:
```bash
# After running docker compose up, run these bucket setup steps once:
# docker compose exec seaweedfs-master weed shell -master=localhost:9333
# > s3.bucket.create -name raw-flights
# > s3.bucket.create -name frontend-exports
# > s3.configure -access_key=admin -secret_key=admin -actions=Read,Write,List,Tagging -apply
# > s3.configure -buckets=frontend-exports -access_key="" -secret_key="" -actions=Read,List -apply
```

---

## Task 3: Dagster project scaffold

**Files:**
- Create: `pipeline/pyproject.toml`
- Create: `pipeline/Dockerfile`
- Create: `pipeline/pipeline/__init__.py`
- Create: `pipeline/pipeline/config.py`

- [ ] **Step 1: Write `pipeline/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:BuildBackend"

[project]
name = "travel_pal_pipeline"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "dagster>=1.9",
    "dagster-postgres",
    "dagster-dbt",
    "dbt-duckdb>=1.9",
    "duckdb>=1.4.0",
    "pyiceberg[s3fs,nessie]>=0.8",
    "boto3",
    "httpx",
    "pyarrow>=15",
    "sqlglot>=25",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "moto[s3]",
]

[tool.dagster]
module_name = "pipeline"
```

- [ ] **Step 2: Write `pipeline/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /opt/dagster/app

COPY pyproject.toml .
RUN pip install -e ".[dev]"

COPY pipeline/ pipeline/
COPY transforms/ transforms/
```

- [ ] **Step 3: Write `pipeline/pipeline/config.py`**

```python
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class PipelineConfig:
    airport_icao: str
    ingest_start_date: str
    ingest_end_date: str
    seaweedfs_endpoint: str
    seaweedfs_access_key: str
    seaweedfs_secret_key: str
    nessie_endpoint: str
    raw_bucket: str = "raw-flights"
    export_bucket: str = "frontend-exports"

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls(
            airport_icao=os.environ["AIRPORT_ICAO"],
            ingest_start_date=os.environ["INGEST_START_DATE"],
            ingest_end_date=os.environ["INGEST_END_DATE"],
            seaweedfs_endpoint=os.environ["SEAWEEDFS_S3_ENDPOINT"],
            seaweedfs_access_key=os.environ["SEAWEEDFS_ACCESS_KEY"],
            seaweedfs_secret_key=os.environ["SEAWEEDFS_SECRET_KEY"],
            nessie_endpoint=os.environ["NESSIE_ENDPOINT"],
        )
```

- [ ] **Step 4: Write failing test for config**

Create `pipeline/tests/__init__.py` (empty) and `pipeline/tests/test_config.py`:

```python
import os
import pytest
from pipeline.config import PipelineConfig


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-12-31")
    monkeypatch.setenv("SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/api/v1")

    config = PipelineConfig.from_env()

    assert config.airport_icao == "KJFK"
    assert config.raw_bucket == "raw-flights"
    assert config.export_bucket == "frontend-exports"


def test_config_missing_env_raises(monkeypatch):
    monkeypatch.delenv("AIRPORT_ICAO", raising=False)
    with pytest.raises(KeyError):
        PipelineConfig.from_env()
```

- [ ] **Step 5: Run test to verify it fails**

```bash
cd pipeline && pip install -e ".[dev]" && pytest tests/test_config.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'pipeline'`

- [ ] **Step 6: Write `pipeline/pipeline/__init__.py`** (Dagster Definitions — stub for now)

```python
from dagster import Definitions

defs = Definitions(assets=[])
```

- [ ] **Step 7: Run test to verify it passes**

```bash
cd pipeline && pytest tests/test_config.py -v
```

Expected: `2 passed`

- [ ] **Step 8: Commit**

```bash
git add pipeline/
git commit -m "chore: scaffold dagster project with config and pyproject.toml"
```

---

## Task 4: OpenSky source adapter

**Files:**
- Create: `pipeline/pipeline/resources/opensky.py`
- Create: `pipeline/tests/test_opensky.py`

The OpenSky REST API for historical airport arrivals/departures:
- Departures: `GET https://opensky-network.org/api/flights/departure?airport={icao}&begin={unix}&end={unix}`
- Arrivals: `GET https://opensky-network.org/api/flights/arrival?airport={icao}&begin={unix}&end={unix}`
- Returns JSON array. Max window per request: 7 days. No auth required for anonymous (rate-limited to ~100 req/day).

- [ ] **Step 1: Write failing test**

```python
# pipeline/tests/test_opensky.py
import pytest
import pyarrow as pa
from unittest.mock import patch, MagicMock
from pipeline.resources.opensky import OpenSkyAdapter, FlightRecord


SAMPLE_RESPONSE = [
    {
        "icao24": "a1b2c3",
        "firstSeen": 1704067200,
        "estDepartureAirport": "KJFK",
        "lastSeen": 1704074400,
        "estArrivalAirport": "KLAX",
        "callsign": "AA100   ",
        "estDepartureAirportHorizDistance": 500,
        "estDepartureAirportVertDistance": 50,
        "estArrivalAirportHorizDistance": 600,
        "estArrivalAirportVertDistance": 60,
        "departureAirportCandidatesCount": 1,
        "arrivalAirportCandidatesCount": 1,
    }
]


def test_fetch_departures_returns_arrow_table():
    adapter = OpenSkyAdapter()
    with patch("pipeline.resources.opensky.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SAMPLE_RESPONSE,
            raise_for_status=lambda: None,
        )
        table = adapter.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    assert isinstance(table, pa.Table)
    assert "icao24" in table.column_names
    assert "callsign" in table.column_names
    assert "first_seen" in table.column_names
    assert table.num_rows == 1


def test_callsign_is_stripped():
    adapter = OpenSkyAdapter()
    with patch("pipeline.resources.opensky.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SAMPLE_RESPONSE,
            raise_for_status=lambda: None,
        )
        table = adapter.fetch_departures("KJFK", "2024-01-01", "2024-01-07")

    assert table.column("callsign")[0].as_py() == "AA100"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pipeline && pytest tests/test_opensky.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'pipeline.resources'`

- [ ] **Step 3: Write `pipeline/pipeline/resources/__init__.py`** (empty)

```python
```

- [ ] **Step 4: Write `pipeline/pipeline/resources/opensky.py`**

```python
from dataclasses import dataclass
from datetime import datetime, date
import httpx
import pyarrow as pa


BASE_URL = "https://opensky-network.org/api/flights"


@dataclass
class FlightRecord:
    icao24: str
    callsign: str
    first_seen: int
    last_seen: int
    est_departure_airport: str | None
    est_arrival_airport: str | None


class OpenSkyAdapter:
    """Thin adapter over the OpenSky REST API. Swap this file to change data source."""

    def fetch_departures(
        self, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        begin = int(datetime.fromisoformat(start_date).timestamp())
        end = int(datetime.fromisoformat(end_date).timestamp())
        response = httpx.get(
            f"{BASE_URL}/departure",
            params={"airport": airport_icao, "begin": begin, "end": end},
            timeout=30,
        )
        response.raise_for_status()
        return self._to_arrow(response.json())

    def fetch_arrivals(
        self, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        begin = int(datetime.fromisoformat(start_date).timestamp())
        end = int(datetime.fromisoformat(end_date).timestamp())
        response = httpx.get(
            f"{BASE_URL}/arrival",
            params={"airport": airport_icao, "begin": begin, "end": end},
            timeout=30,
        )
        response.raise_for_status()
        return self._to_arrow(response.json())

    def _to_arrow(self, records: list[dict]) -> pa.Table:
        return pa.table(
            {
                "icao24": [r["icao24"] for r in records],
                "callsign": [r.get("callsign", "").strip() for r in records],
                "first_seen": [r["firstSeen"] for r in records],
                "last_seen": [r["lastSeen"] for r in records],
                "est_departure_airport": [
                    r.get("estDepartureAirport") for r in records
                ],
                "est_arrival_airport": [r.get("estArrivalAirport") for r in records],
            }
        )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd pipeline && pytest tests/test_opensky.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add pipeline/pipeline/resources/
git add pipeline/tests/test_opensky.py
git commit -m "feat: add OpenSky source adapter with Arrow output"
```

---

## Task 5: SeaweedFS and Nessie resources

**Files:**
- Create: `pipeline/pipeline/resources/seaweedfs.py`
- Create: `pipeline/pipeline/resources/nessie.py`
- Create: `pipeline/tests/test_resources.py`

- [ ] **Step 1: Write failing tests**

```python
# pipeline/tests/test_resources.py
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from unittest.mock import patch, MagicMock
from pipeline.resources.seaweedfs import SeaweedFSResource
from pipeline.resources.nessie import NessieResource


def test_seaweedfs_upload_parquet(tmp_path):
    resource = SeaweedFSResource(
        endpoint="http://localhost:8333",
        access_key="admin",
        secret_key="admin",
    )
    table = pa.table({"icao24": ["abc"], "callsign": ["AA1"]})

    with patch("pipeline.resources.seaweedfs.boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        resource.upload_parquet(table, bucket="raw-flights", key="test/data.parquet")

    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "raw-flights"
    assert call_kwargs["Key"] == "test/data.parquet"


def test_nessie_resource_init():
    resource = NessieResource(endpoint="http://localhost:19120/api/v1")
    assert resource.endpoint == "http://localhost:19120/api/v1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pipeline && pytest tests/test_resources.py -v
```

Expected: `FAILED` — `ModuleNotFoundError`

- [ ] **Step 3: Write `pipeline/pipeline/resources/seaweedfs.py`**

```python
import io
import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from dataclasses import dataclass


@dataclass
class SeaweedFSResource:
    endpoint: str
    access_key: str
    secret_key: str

    def _client(self):
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    def upload_parquet(self, table: pa.Table, bucket: str, key: str) -> None:
        buf = io.BytesIO()
        pq.write_table(table, buf)
        buf.seek(0)
        self._client().put_object(Bucket=bucket, Key=key, Body=buf.read())

    def get_public_url(self, bucket: str, key: str) -> str:
        return f"{self.endpoint}/{bucket}/{key}"
```

- [ ] **Step 4: Write `pipeline/pipeline/resources/nessie.py`**

```python
from dataclasses import dataclass
from pyiceberg.catalog import load_catalog


@dataclass
class NessieResource:
    endpoint: str

    def catalog(self):
        return load_catalog(
            "nessie",
            **{
                "type": "rest",
                "uri": self.endpoint,
                "warehouse": "s3://raw-flights/warehouse",
            },
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd pipeline && pytest tests/test_resources.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add pipeline/pipeline/resources/seaweedfs.py pipeline/pipeline/resources/nessie.py
git add pipeline/tests/test_resources.py
git commit -m "feat: add SeaweedFS and Nessie catalog resources"
```

---

## Task 6: `raw_flights` Dagster asset

**Files:**
- Create: `pipeline/pipeline/assets/raw_flights.py`
- Create: `pipeline/pipeline/assets/__init__.py`
- Create: `pipeline/tests/test_asset_raw_flights.py`

This asset fetches OpenSky data in 7-day chunks (API limit), uploads Parquet to SeaweedFS, and registers the table in Nessie.

- [ ] **Step 1: Write failing test**

```python
# pipeline/tests/test_asset_raw_flights.py
import pytest
import pyarrow as pa
from unittest.mock import MagicMock, patch
from pipeline.assets.raw_flights import raw_flights
from pipeline.config import PipelineConfig


SAMPLE_TABLE = pa.table(
    {
        "icao24": ["a1b2c3"],
        "callsign": ["AA100"],
        "first_seen": [1704067200],
        "last_seen": [1704074400],
        "est_departure_airport": ["KJFK"],
        "est_arrival_airport": ["KLAX"],
    }
)


def test_raw_flights_asset_uploads_and_registers(monkeypatch):
    config = PipelineConfig(
        airport_icao="KJFK",
        ingest_start_date="2024-01-01",
        ingest_end_date="2024-01-08",
        seaweedfs_endpoint="http://localhost:8333",
        seaweedfs_access_key="admin",
        seaweedfs_secret_key="admin",
        nessie_endpoint="http://localhost:19120/api/v1",
    )
    mock_opensky = MagicMock()
    mock_opensky.fetch_departures.return_value = SAMPLE_TABLE
    mock_opensky.fetch_arrivals.return_value = SAMPLE_TABLE

    mock_seaweedfs = MagicMock()
    mock_nessie = MagicMock()
    mock_catalog = MagicMock()
    mock_nessie.catalog.return_value = mock_catalog

    result = raw_flights(
        config=config,
        opensky=mock_opensky,
        seaweedfs=mock_seaweedfs,
        nessie=mock_nessie,
    )

    assert mock_seaweedfs.upload_parquet.called
    assert result is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pipeline && pytest tests/test_asset_raw_flights.py -v
```

Expected: `FAILED` — `ModuleNotFoundError`

- [ ] **Step 3: Write `pipeline/pipeline/assets/__init__.py`** (empty)

```python
```

- [ ] **Step 4: Write `pipeline/pipeline/assets/raw_flights.py`**

```python
import pyarrow as pa
from datetime import date, timedelta
from dagster import asset, AssetExecutionContext, Config
from pipeline.config import PipelineConfig
from pipeline.resources.opensky import OpenSkyAdapter
from pipeline.resources.seaweedfs import SeaweedFSResource
from pipeline.resources.nessie import NessieResource


def _date_chunks(start: str, end: str, days: int = 7):
    current = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    while current < end_date:
        chunk_end = min(current + timedelta(days=days), end_date)
        yield current.isoformat(), chunk_end.isoformat()
        current = chunk_end


@asset
def raw_flights(
    config: PipelineConfig,
    opensky: OpenSkyAdapter,
    seaweedfs: SeaweedFSResource,
    nessie: NessieResource,
) -> pa.Table:
    tables: list[pa.Table] = []

    for chunk_start, chunk_end in _date_chunks(
        config.ingest_start_date, config.ingest_end_date
    ):
        departures = opensky.fetch_departures(
            config.airport_icao, chunk_start, chunk_end
        )
        arrivals = opensky.fetch_arrivals(
            config.airport_icao, chunk_start, chunk_end
        )
        tables.extend([departures, arrivals])

    combined = pa.concat_tables(tables)
    key = f"{config.airport_icao}/raw_flights.parquet"
    seaweedfs.upload_parquet(combined, bucket=config.raw_bucket, key=key)

    catalog = nessie.catalog()
    if not catalog.table_exists("flights.raw_flights"):
        import pyiceberg.schema as sch
        from pyiceberg.types import (
            NestedField, StringType, LongType
        )
        schema = sch.Schema(
            NestedField(1, "icao24", StringType(), required=False),
            NestedField(2, "callsign", StringType(), required=False),
            NestedField(3, "first_seen", LongType(), required=False),
            NestedField(4, "last_seen", LongType(), required=False),
            NestedField(5, "est_departure_airport", StringType(), required=False),
            NestedField(6, "est_arrival_airport", StringType(), required=False),
        )
        catalog.create_namespace_if_not_exists("flights")
        catalog.create_table("flights.raw_flights", schema=schema)

    return combined
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd pipeline && pytest tests/test_asset_raw_flights.py -v
```

Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
git add pipeline/pipeline/assets/
git add pipeline/tests/test_asset_raw_flights.py
git commit -m "feat: add raw_flights dagster asset (opensky fetch + seaweedfs + nessie)"
```

---

## Task 7: dbt project and SQL models

**Files:**
- Create: `pipeline/transforms/dbt_project.yml`
- Create: `pipeline/transforms/profiles.yml`
- Create: `pipeline/transforms/models/staging/stg_flights.sql`
- Create: `pipeline/transforms/models/intermediate/fct_flight_performance.sql`
- Create: `pipeline/transforms/models/marts/agg_route_timeliness.sql`
- Create: `pipeline/transforms/models/marts/agg_daily_timeliness.sql`
- Create: `pipeline/transforms/tests/stg_flights_not_null.yml`

All SQL is written in ANSI dialect. sqlglot transpiles it to DuckDB dialect at build time (Task 8).

- [ ] **Step 1: Write `pipeline/transforms/dbt_project.yml`**

```yaml
name: travel_pal
version: "1.0.0"
config-version: 2
profile: travel_pal

model-paths: ["models"]
test-paths: ["tests"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]

models:
  travel_pal:
    staging:
      +materialized: view
    intermediate:
      +materialized: table
    marts:
      +materialized: table
```

- [ ] **Step 2: Write `pipeline/transforms/profiles.yml`**

```yaml
travel_pal:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "{{ env_var('DBT_DUCKDB_PATH', '/tmp/travel_pal.duckdb') }}"
      extensions:
        - httpfs
        - iceberg
      settings:
        s3_endpoint: "{{ env_var('SEAWEEDFS_S3_ENDPOINT', 'localhost:8333') }}"
        s3_access_key_id: "{{ env_var('SEAWEEDFS_ACCESS_KEY', 'admin') }}"
        s3_secret_access_key: "{{ env_var('SEAWEEDFS_SECRET_KEY', 'admin') }}"
        s3_use_ssl: false
        s3_url_style: path
```

- [ ] **Step 3: Write `models/staging/stg_flights.sql`** (ANSI SQL)

```sql
-- Staging: cast and clean raw OpenSky fields
SELECT
    icao24,
    TRIM(callsign)                                  AS callsign,
    CAST(first_seen AS TIMESTAMP)                   AS departed_at,
    CAST(last_seen  AS TIMESTAMP)                   AS arrived_at,
    est_departure_airport                           AS origin_icao,
    est_arrival_airport                             AS destination_icao
FROM {{ source('raw', 'raw_flights') }}
WHERE icao24 IS NOT NULL
  AND callsign IS NOT NULL
  AND first_seen IS NOT NULL
  AND last_seen  IS NOT NULL
```

- [ ] **Step 4: Write `models/intermediate/fct_flight_performance.sql`** (ANSI SQL)

```sql
-- Fact: one row per flight with computed delay metrics
-- NOTE: OpenSky does not provide scheduled times; last_seen - first_seen = block time.
-- Delay is approximated as block_minutes vs. route median (computed in agg models).
SELECT
    icao24,
    callsign,
    origin_icao,
    destination_icao,
    departed_at,
    arrived_at,
    CAST(
        (EXTRACT(EPOCH FROM arrived_at) - EXTRACT(EPOCH FROM departed_at)) / 60
        AS INTEGER
    )                                               AS block_minutes,
    CASE
        WHEN arrived_at IS NULL THEN TRUE
        ELSE FALSE
    END                                             AS is_cancelled
FROM {{ ref('stg_flights') }}
```

- [ ] **Step 5: Write `models/marts/agg_route_timeliness.sql`** (ANSI SQL)

```sql
-- Aggregate: per-route timeliness metrics
-- on_time_ratio uses ≤15-minute variance from route median block time
WITH route_medians AS (
    SELECT
        origin_icao,
        destination_icao,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY block_minutes) AS median_block_minutes
    FROM {{ ref('fct_flight_performance') }}
    WHERE is_cancelled = FALSE
    GROUP BY origin_icao, destination_icao
),
with_delay AS (
    SELECT
        f.*,
        f.block_minutes - m.median_block_minutes AS delay_minutes
    FROM {{ ref('fct_flight_performance') }} f
    JOIN route_medians m
        ON f.origin_icao = m.origin_icao
       AND f.destination_icao = m.destination_icao
    WHERE f.is_cancelled = FALSE
)
SELECT
    origin_icao,
    destination_icao,
    COUNT(*)                                                    AS total_flights,
    ROUND(AVG(delay_minutes), 1)                                AS avg_delay_minutes,
    ROUND(STDDEV(delay_minutes), 1)                             AS delay_volatility,
    ROUND(
        SUM(CASE WHEN delay_minutes <= 15 THEN 1 ELSE 0 END) * 1.0 / COUNT(*),
        3
    )                                                           AS on_time_ratio,
    ROUND(
        SUM(CASE WHEN f2.is_cancelled THEN 1 ELSE 0 END) * 1.0
            / (COUNT(*) + SUM(CASE WHEN f2.is_cancelled THEN 1 ELSE 0 END)),
        3
    )                                                           AS cancellation_rate
FROM with_delay wd
JOIN {{ ref('fct_flight_performance') }} f2
    ON wd.origin_icao = f2.origin_icao
   AND wd.destination_icao = f2.destination_icao
GROUP BY origin_icao, destination_icao
```

- [ ] **Step 6: Write `models/marts/agg_daily_timeliness.sql`** (ANSI SQL)

```sql
-- Aggregate: per-day timeliness for the dashboard
WITH daily AS (
    SELECT
        CAST(departed_at AS DATE)   AS flight_date,
        origin_icao,
        block_minutes,
        is_cancelled
    FROM {{ ref('fct_flight_performance') }}
),
daily_medians AS (
    SELECT
        flight_date,
        origin_icao,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY block_minutes) AS median_block
    FROM daily
    WHERE is_cancelled = FALSE
    GROUP BY flight_date, origin_icao
)
SELECT
    d.flight_date,
    d.origin_icao,
    COUNT(*)                                                        AS total_flights,
    ROUND(AVG(d.block_minutes - m.median_block), 1)                AS avg_delay_minutes,
    ROUND(STDDEV(d.block_minutes - m.median_block), 1)             AS delay_volatility,
    ROUND(
        SUM(CASE WHEN (d.block_minutes - m.median_block) <= 15 THEN 1 ELSE 0 END)
            * 1.0 / NULLIF(SUM(CASE WHEN NOT d.is_cancelled THEN 1 ELSE 0 END), 0),
        3
    )                                                               AS on_time_ratio,
    ROUND(
        SUM(CASE WHEN d.is_cancelled THEN 1 ELSE 0 END) * 1.0 / COUNT(*),
        3
    )                                                               AS cancellation_rate
FROM daily d
LEFT JOIN daily_medians m
    ON d.flight_date = m.flight_date
   AND d.origin_icao = m.origin_icao
WHERE NOT d.is_cancelled
GROUP BY d.flight_date, d.origin_icao
ORDER BY d.flight_date
```

- [ ] **Step 7: Write `models/staging/sources.yml`** — required for `{{ source('raw', 'raw_flights') }}` references in stg_flights.sql

```yaml
version: 2

sources:
  - name: raw
    schema: main
    tables:
      - name: raw_flights
        description: Raw flight records fetched from OpenSky Network
        columns:
          - name: icao24
            tests:
              - not_null
          - name: first_seen
            tests:
              - not_null
```

- [ ] **Step 8: Write dbt schema tests `tests/stg_flights_not_null.yml`**

```yaml
version: 2

models:
  - name: stg_flights
    columns:
      - name: icao24
        tests:
          - not_null
      - name: callsign
        tests:
          - not_null
      - name: departed_at
        tests:
          - not_null

  - name: agg_route_timeliness
    columns:
      - name: on_time_ratio
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 1
```

- [ ] **Step 9: Run dbt compile to verify SQL parses**

```bash
cd pipeline/transforms
DBT_DUCKDB_PATH=/tmp/tp_test.duckdb dbt compile
```

Expected: `Compiled 4 models` with no errors.

- [ ] **Step 10: Commit**

```bash
git add pipeline/transforms/
git commit -m "feat: add dbt models (stg, fct, agg_route, agg_daily) in ANSI SQL"
```

---

## Task 8: sqlglot transpiler

**Files:**
- Create: `transpiler/transpile.py`
- Create: `transpiler/tests/test_transpile.py`

Reads all `.sql` files from `pipeline/transforms/models/`, transpiles ANSI → DuckDB dialect, writes output to `frontend/public/sql/`.

- [ ] **Step 1: Write failing test**

```python
# transpiler/tests/test_transpile.py
import pytest
from transpiler.transpile import transpile_sql, transpile_directory
from pathlib import Path


def test_transpile_cast_to_duckdb():
    ansi_sql = "SELECT CAST(first_seen AS TIMESTAMP) FROM flights"
    result = transpile_sql(ansi_sql)
    assert "TIMESTAMP" in result
    assert isinstance(result, str)
    assert len(result) > 0


def test_transpile_preserves_select_columns():
    ansi_sql = "SELECT icao24, callsign FROM stg_flights WHERE icao24 IS NOT NULL"
    result = transpile_sql(ansi_sql)
    assert "icao24" in result
    assert "callsign" in result
    assert "stg_flights" in result


def test_transpile_directory(tmp_path):
    sql_dir = tmp_path / "models"
    sql_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (sql_dir / "test_model.sql").write_text(
        "SELECT CAST(x AS INTEGER) FROM t"
    )

    transpile_directory(sql_dir, out_dir)

    result_file = out_dir / "test_model.sql"
    assert result_file.exists()
    content = result_file.read_text()
    assert "SELECT" in content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd transpiler && pip install sqlglot && pytest tests/test_transpile.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'transpiler'`

- [ ] **Step 3: Write `transpiler/transpile.py`**

```python
import sqlglot
from pathlib import Path


def transpile_sql(ansi_sql: str) -> str:
    statements = sqlglot.transpile(ansi_sql, read="", write="duckdb")
    return ";\n".join(statements)


def transpile_directory(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for sql_file in src.rglob("*.sql"):
        transpiled = transpile_sql(sql_file.read_text())
        out_file = dst / sql_file.name
        out_file.write_text(transpiled)
```

- [ ] **Step 4: Create `transpiler/__init__.py`** (empty)

```python
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd transpiler && pytest tests/test_transpile.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Wire transpiler into Vite build**

Add to `frontend/vite.config.ts` (created in Task 9) a pre-build plugin that runs `python transpiler/transpile.py`. For now, create the CLI entry point:

Add to `transpiler/transpile.py`:
```python
if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pipeline/transforms/models")
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("frontend/public/sql")
    transpile_directory(src, dst)
    print(f"Transpiled SQL from {src} → {dst}")
```

- [ ] **Step 7: Run transpiler manually to verify output**

```bash
python transpiler/transpile.py pipeline/transforms/models frontend/public/sql
ls frontend/public/sql/
```

Expected: `stg_flights.sql`, `fct_flight_performance.sql`, `agg_route_timeliness.sql`, `agg_daily_timeliness.sql` present in `frontend/public/sql/`.

- [ ] **Step 8: Commit**

```bash
git add transpiler/
git add frontend/public/sql/
git commit -m "feat: add sqlglot ANSI→DuckDB transpiler with CLI entry point"
```

---

## Task 9: `transformed_flights` and `frontend_exports` Dagster assets

**Files:**
- Create: `pipeline/pipeline/assets/transformed_flights.py`
- Create: `pipeline/pipeline/assets/frontend_exports.py`
- Create: `pipeline/tests/test_asset_transformed_flights.py`

- [ ] **Step 1: Write failing test**

```python
# pipeline/tests/test_asset_transformed_flights.py
import pytest
import pyarrow as pa
from unittest.mock import MagicMock, patch
from pipeline.assets.transformed_flights import transformed_flights
from pipeline.assets.frontend_exports import frontend_exports
from pipeline.config import PipelineConfig


CONFIG = PipelineConfig(
    airport_icao="KJFK",
    ingest_start_date="2024-01-01",
    ingest_end_date="2024-01-08",
    seaweedfs_endpoint="http://localhost:8333",
    seaweedfs_access_key="admin",
    seaweedfs_secret_key="admin",
    nessie_endpoint="http://localhost:19120/api/v1",
)

AGG_TABLE = pa.table(
    {
        "origin_icao": ["KJFK"],
        "destination_icao": ["KLAX"],
        "total_flights": [100],
        "avg_delay_minutes": [5.2],
        "delay_volatility": [12.1],
        "on_time_ratio": [0.82],
        "cancellation_rate": [0.03],
    }
)


def test_transformed_flights_runs_dbt(monkeypatch):
    mock_seaweedfs = MagicMock()
    with patch("pipeline.assets.transformed_flights.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = transformed_flights(
            config=CONFIG,
            raw_flights=pa.table({"icao24": ["x"]}),
            seaweedfs=mock_seaweedfs,
        )
    mock_run.assert_called_once()
    assert "dbt" in mock_run.call_args.args[0]


def test_frontend_exports_uploads_parquet():
    mock_seaweedfs = MagicMock()
    frontend_exports(
        config=CONFIG,
        transformed_flights=AGG_TABLE,
        seaweedfs=mock_seaweedfs,
    )
    assert mock_seaweedfs.upload_parquet.call_count == 2
    keys = [
        call.kwargs["key"]
        for call in mock_seaweedfs.upload_parquet.call_args_list
    ]
    assert any("route_timeliness" in k for k in keys)
    assert any("daily_timeliness" in k for k in keys)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pipeline && pytest tests/test_asset_transformed_flights.py -v
```

Expected: `FAILED` — `ModuleNotFoundError`

- [ ] **Step 3: Write `pipeline/pipeline/assets/transformed_flights.py`**

```python
import subprocess
import duckdb
import pyarrow as pa
from dagster import asset
from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource


@asset
def transformed_flights(
    config: PipelineConfig,
    raw_flights: pa.Table,
    seaweedfs: SeaweedFSResource,
) -> pa.Table:
    result = subprocess.run(
        ["dbt", "run", "--project-dir", "transforms", "--profiles-dir", "transforms"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt run failed:\n{result.stdout}\n{result.stderr}")

    con = duckdb.connect()
    con.execute("INSTALL iceberg; LOAD iceberg;")
    agg_route = con.execute(
        "SELECT * FROM iceberg_scan('s3://raw-flights/warehouse/flights/agg_route_timeliness')"
    ).arrow()
    return agg_route
```

- [ ] **Step 4: Write `pipeline/pipeline/assets/frontend_exports.py`**

```python
import duckdb
import pyarrow as pa
from dagster import asset
from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource


@asset
def frontend_exports(
    config: PipelineConfig,
    transformed_flights: pa.Table,
    seaweedfs: SeaweedFSResource,
) -> None:
    con = duckdb.connect()
    con.execute("INSTALL iceberg; LOAD iceberg;")

    agg_route = con.execute(
        "SELECT * FROM iceberg_scan('s3://raw-flights/warehouse/flights/agg_route_timeliness')"
    ).arrow()
    seaweedfs.upload_parquet(
        agg_route,
        bucket=config.export_bucket,
        key=f"{config.airport_icao}/route_timeliness.parquet",
    )

    agg_daily = con.execute(
        "SELECT * FROM iceberg_scan('s3://raw-flights/warehouse/flights/agg_daily_timeliness')"
    ).arrow()
    seaweedfs.upload_parquet(
        agg_daily,
        bucket=config.export_bucket,
        key=f"{config.airport_icao}/daily_timeliness.parquet",
    )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd pipeline && pytest tests/test_asset_transformed_flights.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Wire all assets into Dagster Definitions**

Update `pipeline/pipeline/__init__.py`:

```python
from dagster import Definitions
from pipeline.assets.raw_flights import raw_flights
from pipeline.assets.transformed_flights import transformed_flights
from pipeline.assets.frontend_exports import frontend_exports

defs = Definitions(
    assets=[raw_flights, transformed_flights, frontend_exports],
)
```

- [ ] **Step 7: Commit**

```bash
git add pipeline/pipeline/assets/transformed_flights.py
git add pipeline/pipeline/assets/frontend_exports.py
git add pipeline/pipeline/__init__.py
git add pipeline/tests/test_asset_transformed_flights.py
git commit -m "feat: add transformed_flights and frontend_exports dagster assets"
```

---

## Task 10: React + Vite + DuckDB-WASM frontend scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/db/client.ts`
- Create: `frontend/src/db/queries.ts`
- Create: `frontend/index.html`

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "travel-pal-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && python ../transpiler/transpile.py ../pipeline/transforms/models public/sql && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@duckdb/duckdb-wasm": "^1.29.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.11"
  }
}
```

- [ ] **Step 2: Write `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
  },
  server: {
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
})
```

- [ ] **Step 3: Write `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>TravelPal</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Write `frontend/src/main.tsx`**

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

- [ ] **Step 5: Write `frontend/src/App.tsx`** (stub)

```typescript
export default function App() {
  return (
    <main>
      <h1>TravelPal</h1>
      <p>Loading...</p>
    </main>
  )
}
```

- [ ] **Step 6: Write `frontend/src/db/client.ts`**

```typescript
import * as duckdb from '@duckdb/duckdb-wasm'

let db: duckdb.AsyncDuckDB | null = null

const SEAWEEDFS_PUBLIC_BASE =
  import.meta.env.VITE_SEAWEEDFS_PUBLIC_BASE ?? 'http://localhost:8333/frontend-exports'

export async function getDb(): Promise<duckdb.AsyncDuckDB> {
  if (db) return db

  const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles()
  const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES)
  const worker_url = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker!}");`], { type: 'text/javascript' })
  )
  const worker = new Worker(worker_url)
  const logger = new duckdb.ConsoleLogger()
  db = new duckdb.AsyncDuckDB(logger, worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)

  const conn = await db.connect()
  await conn.query('INSTALL httpfs; LOAD httpfs;')
  await conn.query('INSTALL iceberg; LOAD iceberg;')
  await conn.close()

  return db
}

export { SEAWEEDFS_PUBLIC_BASE }
```

- [ ] **Step 7: Write `frontend/src/db/queries.ts`**

```typescript
import { getDb, SEAWEEDFS_PUBLIC_BASE } from './client'

export interface RouteTimeliness {
  origin_icao: string
  destination_icao: string
  total_flights: number
  avg_delay_minutes: number
  delay_volatility: number
  on_time_ratio: number
  cancellation_rate: number
}

export interface DailyTimeliness {
  flight_date: string
  origin_icao: string
  total_flights: number
  avg_delay_minutes: number
  delay_volatility: number
  on_time_ratio: number
  cancellation_rate: number
}

export async function queryRouteTimeliness(
  airportIcao: string
): Promise<RouteTimeliness[]> {
  const db = await getDb()
  const conn = await db.connect()
  const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/route_timeliness.parquet`
  const result = await conn.query(
    `SELECT * FROM read_parquet('${url}') ORDER BY total_flights DESC`
  )
  await conn.close()
  return result.toArray().map((r: any) => r.toJSON())
}

export async function queryFlightLookup(
  airportIcao: string,
  routeOrCallsign: string
): Promise<RouteTimeliness[]> {
  const db = await getDb()
  const conn = await db.connect()
  const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/route_timeliness.parquet`
  // Match against origin, destination, or concatenated route string
  const result = await conn.query(
    `SELECT * FROM read_parquet('${url}')
     WHERE origin_icao ILIKE '%${routeOrCallsign}%'
        OR destination_icao ILIKE '%${routeOrCallsign}%'
     ORDER BY on_time_ratio DESC
     LIMIT 20`
  )
  await conn.close()
  return result.toArray().map((r: any) => r.toJSON())
}

export async function queryDailyTimeliness(
  airportIcao: string
): Promise<DailyTimeliness[]> {
  const db = await getDb()
  const conn = await db.connect()
  const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/daily_timeliness.parquet`
  const result = await conn.query(
    `SELECT * FROM read_parquet('${url}') ORDER BY flight_date`
  )
  await conn.close()
  return result.toArray().map((r: any) => r.toJSON())
}
```

- [ ] **Step 8: Install deps and verify build**

```bash
cd frontend && npm install && npm run build
```

Expected: build succeeds, `dist/` created, no TypeScript errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold react+vite+duckdb-wasm frontend with query layer"
```

---

## Task 11: F1.1 FlightLookup component and F1.2 TimelinessDashboard component

**Files:**
- Create: `frontend/src/components/FlightLookup/FlightLookup.tsx`
- Create: `frontend/src/components/FlightLookup/FlightLookup.css`
- Create: `frontend/src/components/TimelinessDashboard/TimelinessDashboard.tsx`
- Create: `frontend/src/components/TimelinessDashboard/TimelinessDashboard.css`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write `frontend/src/components/FlightLookup/FlightLookup.tsx`**

```typescript
import { useState } from 'react'
import { queryFlightLookup, RouteTimeliness } from '../../db/queries'
import './FlightLookup.css'

interface Props {
  airportIcao: string
}

export default function FlightLookup({ airportIcao }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<RouteTimeliness[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSearch() {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await queryFlightLookup(airportIcao, query.trim().toUpperCase())
      setResults(data)
    } catch (e) {
      setError('Failed to load flight data. Check that the pipeline has run.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="flight-lookup" aria-labelledby="lookup-heading">
      <h2 id="lookup-heading">Flight Lookup</h2>
      <div className="lookup-input-row">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Route (e.g. KJFK) or callsign"
          aria-label="Flight number or route"
        />
        <button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="results-grid">
        {results.map(r => (
          <article key={`${r.origin_icao}-${r.destination_icao}`} className="result-card">
            <h3>{r.origin_icao} → {r.destination_icao}</h3>
            <dl>
              <dt>On-time ratio</dt>
              <dd>{(r.on_time_ratio * 100).toFixed(1)}%</dd>
              <dt>Avg delay</dt>
              <dd>{r.avg_delay_minutes} min</dd>
              <dt>Cancellation rate</dt>
              <dd>{(r.cancellation_rate * 100).toFixed(1)}%</dd>
              <dt>Total flights</dt>
              <dd>{r.total_flights.toLocaleString()}</dd>
            </dl>
          </article>
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 2: Write `frontend/src/components/FlightLookup/FlightLookup.css`**

```css
.flight-lookup {
  max-width: 800px;
  margin: 0 auto;
  padding: var(--space-section, 2rem);
}

.lookup-input-row {
  display: flex;
  gap: 0.5rem;
  margin-block: 1rem;
}

.lookup-input-row input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  font-size: 1rem;
  border: 1px solid currentColor;
}

.lookup-input-row button {
  padding: 0.5rem 1.25rem;
  cursor: pointer;
}

.lookup-input-row button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  color: red;
  margin-block: 0.5rem;
}

.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
  margin-top: 1.5rem;
}

.result-card {
  border: 1px solid currentColor;
  padding: 1rem;
}

.result-card h3 {
  margin-block-end: 0.75rem;
  font-size: 1rem;
}

.result-card dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 1rem;
  margin: 0;
}

.result-card dt {
  opacity: 0.7;
  font-size: 0.85rem;
}

.result-card dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 3: Write `frontend/src/components/TimelinessDashboard/TimelinessDashboard.tsx`**

```typescript
import { useEffect, useState } from 'react'
import { queryDailyTimeliness, DailyTimeliness } from '../../db/queries'
import './TimelinessDashboard.css'

interface Props {
  airportIcao: string
}

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`
}

export default function TimelinessDashboard({ airportIcao }: Props) {
  const [data, setData] = useState<DailyTimeliness[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    queryDailyTimeliness(airportIcao)
      .then(setData)
      .catch(() => setError('Failed to load timeliness data.'))
      .finally(() => setLoading(false))
  }, [airportIcao])

  if (loading) return <p aria-busy="true">Loading timeliness data…</p>
  if (error) return <p role="alert">{error}</p>
  if (data.length === 0) return <p>No data available. Run the pipeline first.</p>

  const avgOnTime =
    data.reduce((sum, d) => sum + d.on_time_ratio, 0) / data.length
  const avgDelay =
    data.reduce((sum, d) => sum + d.avg_delay_minutes, 0) / data.length
  const avgCancellation =
    data.reduce((sum, d) => sum + d.cancellation_rate, 0) / data.length

  return (
    <section className="timeliness-dashboard" aria-labelledby="dashboard-heading">
      <h2 id="dashboard-heading">Historic Timeliness — {airportIcao}</h2>
      <div className="metric-row">
        <div className="metric-card">
          <span className="metric-label">On-time arrival ratio</span>
          <span className="metric-value">{pct(avgOnTime)}</span>
          <span className="metric-sub">≤15 min variance</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Average delay</span>
          <span className="metric-value">{avgDelay.toFixed(1)} min</span>
          <span className="metric-sub">vs. route median</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Cancellation rate</span>
          <span className="metric-value">{pct(avgCancellation)}</span>
          <span className="metric-sub">outright cancellations</span>
        </div>
      </div>
      <table className="daily-table" aria-label="Daily timeliness breakdown">
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Flights</th>
            <th scope="col">On-time %</th>
            <th scope="col">Avg delay (min)</th>
            <th scope="col">Cancellation %</th>
          </tr>
        </thead>
        <tbody>
          {data.map(d => (
            <tr key={d.flight_date}>
              <td>{d.flight_date}</td>
              <td>{d.total_flights.toLocaleString()}</td>
              <td>{pct(d.on_time_ratio)}</td>
              <td>{d.avg_delay_minutes.toFixed(1)}</td>
              <td>{pct(d.cancellation_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
```

- [ ] **Step 4: Write `frontend/src/components/TimelinessDashboard/TimelinessDashboard.css`**

```css
.timeliness-dashboard {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-section, 2rem);
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-block: 1.5rem;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 1rem;
  border: 1px solid currentColor;
}

.metric-label {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  opacity: 0.7;
}

.metric-value {
  font-size: 2rem;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.metric-sub {
  font-size: 0.75rem;
  opacity: 0.6;
}

.daily-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.daily-table th,
.daily-table td {
  padding: 0.5rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid currentColor;
}

.daily-table th {
  opacity: 0.7;
  font-weight: 600;
}

.daily-table tr:hover td {
  opacity: 0.8;
}
```

- [ ] **Step 5: Update `frontend/src/App.tsx` to wire components**

```typescript
import FlightLookup from './components/FlightLookup/FlightLookup'
import TimelinessDashboard from './components/TimelinessDashboard/TimelinessDashboard'

const AIRPORT_ICAO = import.meta.env.VITE_AIRPORT_ICAO ?? 'KJFK'

export default function App() {
  return (
    <main>
      <header>
        <h1>TravelPal</h1>
        <p>Flight performance analytics for {AIRPORT_ICAO}</p>
      </header>
      <TimelinessDashboard airportIcao={AIRPORT_ICAO} />
      <FlightLookup airportIcao={AIRPORT_ICAO} />
    </main>
  )
}
```

- [ ] **Step 6: Verify build passes**

```bash
cd frontend && npm run build
```

Expected: `dist/` built with no TypeScript errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ frontend/src/App.tsx
git commit -m "feat: add FlightLookup (F1.1) and TimelinessDashboard (F1.2) components"
```

---

## Task 12: End-to-end smoke test

Run the full pipeline against real infrastructure and verify the frontend loads data.

- [ ] **Step 1: Start all services**

```bash
docker compose up -d
```

Expected: all 6 services running within 60 seconds. Verify: `docker compose ps`

- [ ] **Step 2: Materialize all Dagster assets**

Open `http://localhost:3000`, navigate to Assets, select all three assets (`raw_flights` → `transformed_flights` → `frontend_exports`), click **Materialize**.

Alternatively via CLI:
```bash
docker compose exec dagster-webserver dagster asset materialize \
  --select "raw_flights+transformed_flights+frontend_exports" \
  -m pipeline
```

Expected: all three assets materialize green. Check Dagster logs for any errors.

- [ ] **Step 3: Verify Parquet files exist in SeaweedFS**

```bash
AWS_ACCESS_KEY_ID=admin AWS_SECRET_ACCESS_KEY=admin \
  aws s3 ls s3://frontend-exports/KJFK/ --endpoint-url http://localhost:8333
```

Expected: `route_timeliness.parquet` and `daily_timeliness.parquet` listed.

- [ ] **Step 4: Start the frontend dev server**

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`. Expected:
- TimelinessDashboard loads with metrics populated (not "No data available")
- FlightLookup accepts input and returns results

- [ ] **Step 5: Run all Python tests**

```bash
cd pipeline && pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "chore: phase 0 complete — full pipeline smoke tested end-to-end"
```

---

## Summary

| Task | Deliverable |
|---|---|
| 1 | Docker Compose: 6 services |
| 2 | SeaweedFS S3 buckets with public-read frontend prefix |
| 3 | Dagster project scaffold + typed config |
| 4 | OpenSky source adapter (swappable interface) |
| 5 | SeaweedFS + Nessie resources |
| 6 | `raw_flights` asset (fetch → upload → register) |
| 7 | dbt models: staging, fact, two aggregates (ANSI SQL) |
| 8 | sqlglot transpiler: ANSI → DuckDB dialect, CLI + Vite integration |
| 9 | `transformed_flights` + `frontend_exports` assets |
| 10 | React + Vite + DuckDB-WASM frontend scaffold |
| 11 | F1.1 FlightLookup + F1.2 TimelinessDashboard |
| 12 | End-to-end smoke test |
