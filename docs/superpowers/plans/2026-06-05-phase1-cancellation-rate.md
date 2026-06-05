# Phase 1 Cancellation Rate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface cancellation-rate metrics for KJFK on the public dashboard, sourced from BTS On-Time Performance, with carrier and route Highcharts bar charts.

**Architecture:** A new Dagster monthly-partitioned asset downloads BTS ZIPs via pyreqwest, lands them as Iceberg `flights.bts_on_time` (PyIceberg). Two dbt seeds (`dim_airport` from OurAirports, `dim_carrier` from OpenFlights) underpin a `stg_bts_on_time` view that translates IATA → ICAO. Two new aggregation marts (`agg_carrier_cancellations`, `agg_route_cancellations`) compute cancellation_rate. `frontend_exports` filters them to the airport and uploads `carrier_cancellations.parquet` + `route_cancellations.parquet` for DuckDB-WASM. A new `<CancellationSection>` component renders two Highcharts horizontal bars below the existing FlightLookup.

**Tech Stack:** Python 3.13, pyreqwest, PyArrow, PyIceberg, dbt-duckdb, Dagster (`MonthlyPartitionsDefinition`), DuckDB-WASM, React 18, Highcharts (free non-commercial license) + highcharts-react-official.

**Spec:** `docs/superpowers/specs/2026-06-05-phase1-cancellation-rate-design.md`

---

## File Map

```
travel_pal/
├── LICENSING.md                                              # NEW: Highcharts non-commercial note
│
├── pipeline/
│   ├── pipeline/
│   │   ├── __init__.py                                       # MODIFY: wire BTSResource + bts_on_time
│   │   ├── config.py                                         # MODIFY: bts_endpoint, bts_fixture_file, bts_cache_bucket
│   │   ├── assets/
│   │   │   ├── __init__.py
│   │   │   ├── bts_on_time.py                                # NEW: monthly partitioned asset
│   │   │   ├── transformed_flights.py                        # MODIFY: AssetIn dependency on bts_on_time
│   │   │   └── frontend_exports.py                           # MODIFY: 2 new marts in maps
│   │   └── resources/
│   │       └── bts.py                                        # NEW: BTSResource
│   │
│   ├── transforms/
│   │   ├── dbt_project.yml                                   # MODIFY: seeds: block
│   │   ├── seeds/
│   │   │   ├── dim_airport.csv                               # NEW: OurAirports projected
│   │   │   └── dim_carrier.csv                               # NEW: OpenFlights airlines.dat
│   │   └── models/
│   │       ├── staging/
│   │       │   ├── stg_bts_on_time.sql                       # NEW
│   │       │   └── schema.yml                                # MODIFY: tests on stg_bts cols
│   │       └── marts/
│   │           ├── agg_carrier_cancellations.sql             # NEW
│   │           └── agg_route_cancellations.sql               # NEW
│   │
│   └── tests/
│       ├── fixtures/
│       │   ├── bts_kjfk_2024_01.csv.zip                      # NEW
│       │   ├── carrier_cancellations.parquet                 # NEW
│       │   └── route_cancellations.parquet                   # NEW
│       ├── test_bts.py                                       # NEW
│       ├── test_asset_bts_on_time.py                         # NEW
│       ├── test_dbt_models.py                                # MODIFY: cancellation marts + seeds
│       ├── test_asset_transformed_flights.py                 # MODIFY: assert dependency on bts_on_time
│       └── integration/
│           ├── test_integration_dbt_build.py                 # MODIFY: assert new marts produced
│           ├── test_integration_iceberg_bts.py               # NEW
│           └── test_integration_bts_download.py              # NEW (gated)
│
└── frontend/
    ├── package.json                                          # MODIFY: highcharts deps
    ├── src/
    │   ├── App.tsx                                           # MODIFY: render CancellationSection
    │   ├── db/
    │   │   └── queries.ts                                    # MODIFY: 2 new query fns + types
    │   └── components/
    │       └── CancellationSection/
    │           ├── CancellationSection.tsx                   # NEW
    │           ├── CarrierBar.tsx                            # NEW
    │           ├── RouteBar.tsx                              # NEW
    │           ├── CancellationSection.css                   # NEW
    │           └── CancellationSection.test.tsx             # NEW
    └── tests/e2e/
        └── smoke.spec.ts                                     # MODIFY: assert cancellation section
```

---

## Working Directory & Setup

All `pytest` and `uv` commands assume `cwd = pipeline/`.
All `npm`/`npx` commands assume `cwd = frontend/`.
All `git` commands assume repo root.

Create a feature branch before Task 1:

```bash
git checkout master
git pull --ff-only
git checkout -b feat/phase1-cancellation-rate
```

---

## Task Sequencing

1. **Tasks 1–2** — License doc + Highcharts dep (small, isolated, unblocks Task 14)
2. **Tasks 3–4** — dbt seeds (small data, no logic, unblocks Task 9–10)
3. **Tasks 5–8** — Pipeline backend (resource → asset → wiring → cache)
4. **Tasks 9–12** — dbt staging + marts + frontend export keys
5. **Task 13** — Integration: real Nessie + SeaweedFS round-trip
6. **Tasks 14–17** — Frontend section + Highcharts wrappers
7. **Task 18** — E2E fixtures + Playwright smoke
8. **Task 19** — Live BTS download (gated)
9. **Task 20** — Spec sign-off, memory update, PR

---

## Task 1: Add Highcharts non-commercial license note

**Files:**
- Create: `LICENSING.md`

- [ ] **Step 1: Create the licensing doc**

```markdown
# Third-Party Licensing Notes

## Highcharts

This project uses [Highcharts](https://www.highcharts.com/) under the **free
non-commercial license**. Highcharts is free for personal use, school websites,
and non-profit organisations. Commercial use requires a paid license — see
https://shop.highcharts.com/.

If TravelPal is later commercialised (paid hosting, paid API access, ad-funded
deployment, B2B SaaS), Highcharts MUST be replaced with an Apache/MIT
alternative (ECharts, Recharts, uPlot) before launch.

## OurAirports (`pipeline/transforms/seeds/dim_airport.csv`)

Public-domain airport reference data from <https://ourairports.com/data/>.
Released under Creative Commons Public Domain Dedication.

## OpenFlights Airlines (`pipeline/transforms/seeds/dim_carrier.csv`)

Airline reference data from <https://openflights.org/data.html>. Released under
the OpenFlights Database License (ODbL). Last upstream update: 2017 — adequate
for established US carriers, may miss recent regional/cargo entrants.

## BTS On-Time Performance

Source: U.S. Department of Transportation Bureau of Transportation Statistics,
<https://transtats.bts.gov/>. Public-domain US government data.
```

- [ ] **Step 2: Commit**

```bash
git add LICENSING.md
git commit -m "docs: add Highcharts non-commercial + dataset license notes"
```

---

## Task 2: Add Highcharts frontend dependency

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install dependencies**

```bash
cd frontend
npm install highcharts@^11.4.8 highcharts-react-official@^3.2.1
cd -
```

- [ ] **Step 2: Verify package.json updated**

```bash
grep -E '"highcharts(-react-official)?":' frontend/package.json
```

Expected output (versions may be newer):
```
    "highcharts": "^11.4.8",
    "highcharts-react-official": "^3.2.1",
```

- [ ] **Step 3: Run frontend build to confirm install is clean**

```bash
cd frontend && npx tsc --noEmit && cd -
```

Expected: exits 0, no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add highcharts + highcharts-react-official deps"
```

---

## Task 3: Add `dim_airport` dbt seed (OurAirports projection)

**Files:**
- Create: `pipeline/transforms/seeds/dim_airport.csv`

- [ ] **Step 1: Download OurAirports airports.csv into a temp file**

```bash
curl -sSL https://davidmegginson.github.io/ourairports-data/airports.csv -o /tmp/ourairports_full.csv
wc -l /tmp/ourairports_full.csv
```

Expected: ~80,000+ lines.

- [ ] **Step 2: Project required columns to seed file using DuckDB**

```bash
mkdir -p pipeline/transforms/seeds
duckdb -c "COPY (
  SELECT
    ident          AS icao,
    iata_code      AS iata,
    name,
    municipality   AS city,
    iso_country    AS country,
    latitude_deg   AS lat,
    longitude_deg  AS lon,
    type           AS airport_type
  FROM read_csv_auto('/tmp/ourairports_full.csv')
  WHERE ident IS NOT NULL AND ident <> ''
) TO 'pipeline/transforms/seeds/dim_airport.csv' (HEADER, DELIMITER ',', QUOTE '\"');"

head -3 pipeline/transforms/seeds/dim_airport.csv
wc -l pipeline/transforms/seeds/dim_airport.csv
```

Expected first lines:
```
icao,iata,name,city,country,lat,lon,airport_type
00A,,"Total Rf Heliport","Bensalem",US,40.07080078125,-74.93360137939453,heliport
00AA,,"Aero B Ranch Airport","Leoti",US,38.704022,-101.473911,small_airport
```
Expected line count: 80000–85000 inclusive of header.

- [ ] **Step 3: Sanity-check KJFK is present**

```bash
grep '^KJFK,' pipeline/transforms/seeds/dim_airport.csv
```

Expected: `KJFK,JFK,"John F Kennedy International Airport","New York",US,...`.

- [ ] **Step 4: Commit**

```bash
git add pipeline/transforms/seeds/dim_airport.csv
git commit -m "feat(dbt): add dim_airport seed (OurAirports projected to icao,iata,name,city,country,lat,lon,type)"
```

---

## Task 4: Add `dim_carrier` dbt seed (OpenFlights projection)

**Files:**
- Create: `pipeline/transforms/seeds/dim_carrier.csv`

- [ ] **Step 1: Download OpenFlights airlines.dat**

```bash
curl -sSL https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat -o /tmp/airlines.dat
wc -l /tmp/airlines.dat
```

Expected: ~6,200 lines.

- [ ] **Step 2: Project to seed CSV using DuckDB**

OpenFlights `airlines.dat` columns (no header):
`AirlineID,Name,Alias,IATA,ICAO,Callsign,Country,Active`

```bash
duckdb -c "COPY (
  SELECT
    column4 AS icao,
    column3 AS iata,
    column1 AS name,
    column5 AS callsign,
    column6 AS country,
    column7 AS active
  FROM read_csv_auto(
    '/tmp/airlines.dat',
    HEADER=false,
    QUOTE='\"',
    ESCAPE='\"',
    NULLSTR='\\N'
  )
  WHERE column4 IS NOT NULL AND column4 <> '' AND column4 <> '-'
) TO 'pipeline/transforms/seeds/dim_carrier.csv' (HEADER, DELIMITER ',', QUOTE '\"');"

head -3 pipeline/transforms/seeds/dim_carrier.csv
wc -l pipeline/transforms/seeds/dim_carrier.csv
```

Expected first lines (order may vary):
```
icao,iata,name,callsign,country,active
135,,"135 Airways","GENERAL",United States,N
1ER,,"1Time Airline",NEXTIME,South Africa,Y
```
Expected line count: ~6,200.

- [ ] **Step 3: Sanity-check major US carriers**

```bash
grep -E '^(AAL|DAL|UAL|JBU),' pipeline/transforms/seeds/dim_carrier.csv
```

Expected: `AAL,AA,"American Airlines",AMERICAN,United States,Y` plus 3 similar lines.

- [ ] **Step 4: Commit**

```bash
git add pipeline/transforms/seeds/dim_carrier.csv
git commit -m "feat(dbt): add dim_carrier seed (OpenFlights airlines.dat, ICAO PK)"
```

---

## Task 5: Configure dbt seeds in `dbt_project.yml`

**Files:**
- Modify: `pipeline/transforms/dbt_project.yml`

- [ ] **Step 1: Write the failing test**

Append to `pipeline/tests/test_dbt_models.py` after the existing `test_dbt_project_wires_setup_iceberg_on_run_start`:

```python
@pytest.mark.unit
def test_dbt_project_configures_seeds() -> None:
    """dbt_project.yml must declare a seeds: block with quote_columns disabled.

    BTS reference data + OurAirports/OpenFlights all use unquoted commas inside
    quoted fields; +quote_columns:false lets DuckDB infer types directly from
    the CSV without forcing every column to varchar.
    """
    dbt_project = yaml.safe_load((TRANSFORMS_DIR / "dbt_project.yml").read_text())
    seeds = dbt_project.get("seeds", {})
    travel_pal_seeds = seeds.get("travel_pal", {})
    assert travel_pal_seeds.get("+quote_columns") is False, (
        "seeds.travel_pal.+quote_columns must be false so DuckDB infers "
        "numeric types from dim_airport.lat/lon and dim_carrier.iata"
    )


@pytest.mark.unit
def test_dbt_seeds_present() -> None:
    """The dim_airport and dim_carrier seeds must exist with ICAO as the first column."""
    seeds_dir = TRANSFORMS_DIR / "seeds"
    for seed in ("dim_airport.csv", "dim_carrier.csv"):
        path = seeds_dir / seed
        assert path.exists(), f"transforms/seeds/{seed} must exist"
        first_line = path.read_text().splitlines()[0]
        assert first_line.split(",")[0] == "icao", (
            f"{seed} first column must be 'icao' (canonical PK across the warehouse)"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pipeline
uv run pytest tests/test_dbt_models.py::test_dbt_project_configures_seeds tests/test_dbt_models.py::test_dbt_seeds_present -v
```

Expected: `test_dbt_project_configures_seeds` FAILs with `AssertionError: ... +quote_columns ...`. `test_dbt_seeds_present` PASSes (Tasks 3+4 already added the files).

- [ ] **Step 3: Edit `pipeline/transforms/dbt_project.yml`**

Append after the existing `models:` block:

```yaml
seeds:
  travel_pal:
    +quote_columns: false
    +schema: ref
```

Final file content:

```yaml
name: travel_pal
version: "1.0.0"
config-version: 2
profile: travel_pal

model-paths: ["models"]
macro-paths: ["macros"]
test-paths: ["tests"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]

on-run-start:
  - "{{ setup_iceberg() }}"

models:
  travel_pal:
    staging:
      +materialized: view
    intermediate:
      +materialized: table
    marts:
      +materialized: external
      +format: parquet

seeds:
  travel_pal:
    +quote_columns: false
    +schema: ref
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_dbt_models.py::test_dbt_project_configures_seeds tests/test_dbt_models.py::test_dbt_seeds_present -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/transforms/dbt_project.yml pipeline/tests/test_dbt_models.py
git commit -m "feat(dbt): configure seeds block (quote_columns false, schema ref)"
```

---

## Task 6: Extend `PipelineConfig` with BTS settings

**Files:**
- Modify: `pipeline/pipeline/config.py`
- Modify: `pipeline/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `pipeline/tests/test_config.py`:

```python
def test_pipeline_config_has_bts_settings_with_defaults(monkeypatch):
    """PipelineConfig must expose bts_endpoint (default to BTS prezip URL),
    bts_fixture_file (None by default), and bts_cache_bucket ('bts-raw' default).
    """
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-01-08")
    monkeypatch.setenv("SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/iceberg/")

    cfg = PipelineConfig.from_env()

    assert cfg.bts_endpoint == "https://transtats.bts.gov/PREZIP"
    assert cfg.bts_fixture_file is None
    assert cfg.bts_cache_bucket == "bts-raw"


def test_pipeline_config_bts_fixture_file_overrides(monkeypatch, tmp_path):
    """When BTS_FIXTURE_FILE env var is set, the corresponding field is populated."""
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-01-08")
    monkeypatch.setenv("SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/iceberg/")
    fixture = tmp_path / "bts.zip"
    fixture.write_bytes(b"PK\x03\x04")  # minimal ZIP magic bytes
    monkeypatch.setenv("BTS_FIXTURE_FILE", str(fixture))

    cfg = PipelineConfig.from_env()

    assert cfg.bts_fixture_file == fixture
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd pipeline
uv run pytest tests/test_config.py::test_pipeline_config_has_bts_settings_with_defaults tests/test_config.py::test_pipeline_config_bts_fixture_file_overrides -v
```

Expected: FAIL with `AttributeError: 'PipelineConfig' object has no attribute 'bts_endpoint'`.

- [ ] **Step 3: Update `pipeline/pipeline/config.py`**

Replace contents with:

```python
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineConfig(BaseSettings):
    airport_icao: str
    ingest_start_date: str
    ingest_end_date: str
    seaweedfs_endpoint: str = Field(validation_alias="SEAWEEDFS_S3_ENDPOINT")
    seaweedfs_access_key: str
    seaweedfs_secret_key: str
    nessie_endpoint: str
    raw_bucket: str = "raw-flights"
    export_bucket: str = "frontend-exports"
    opensky_client_id: str = ""
    opensky_client_secret: str = ""

    # Phase 1 — BTS On-Time Performance ingestion
    bts_endpoint: str = "https://transtats.bts.gov/PREZIP"
    bts_fixture_file: Path | None = None
    bts_cache_bucket: str = "bts-raw"

    model_config = SettingsConfigDict(frozen=True, case_sensitive=False)

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls()  # ty: ignore[missing-argument]  # BaseSettings reads env
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: all `test_config.py` tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/pipeline/config.py pipeline/tests/test_config.py
git commit -m "feat(config): add bts_endpoint, bts_fixture_file, bts_cache_bucket settings"
```

---

## Task 7: Build BTS fixture ZIP

**Files:**
- Create: `pipeline/tests/fixtures/bts_kjfk_2024_01.csv.zip`

- [ ] **Step 1: Write a Python helper that generates the fixture ZIP**

Create `pipeline/tests/fixtures/_make_bts_fixture.py`:

```python
"""One-off generator for the BTS test fixture.

Run once and commit the output ZIP. Re-run only if the BTS schema changes.
This file is part of the test fixture set, not production code.
"""

import csv
import io
import zipfile
from pathlib import Path

ROWS = [
    # FlightDate, Reporting_Airline, Tail_Number, Flight_Number_Reporting_Airline,
    # Origin, Dest, CRSDepTime, Cancelled, CancellationCode, Diverted
    ("2024-01-01", "AA", "N123AA", "100", "JFK", "LAX", "0700", "0.00", "",  "0.00"),
    ("2024-01-01", "AA", "N124AA", "101", "JFK", "ORD", "0800", "1.00", "B", "0.00"),
    ("2024-01-02", "AA", "N125AA", "102", "JFK", "MIA", "0900", "0.00", "",  "0.00"),
    ("2024-01-02", "DL", "N201DL", "201", "JFK", "ATL", "0710", "0.00", "",  "0.00"),
    ("2024-01-03", "DL", "N202DL", "202", "JFK", "SEA", "0810", "1.00", "A", "0.00"),
    ("2024-01-03", "DL", "N203DL", "203", "LAX", "JFK", "0900", "0.00", "",  "0.00"),
    ("2024-01-04", "AA", "N126AA", "103", "ORD", "JFK", "1000", "0.00", "",  "1.00"),
    ("2024-01-04", "DL", "N204DL", "204", "JFK", "BOS", "1100", "1.00", "C", "0.00"),
    # Row that should be filtered out (LAX→ORD, no JFK):
    ("2024-01-05", "UA", "N301UA", "301", "LAX", "ORD", "1200", "0.00", "",  "0.00"),
    # Row with unknown IATA codes (should drop in stg, kept in raw):
    ("2024-01-05", "AA", "N127AA", "104", "JFK", "ZZZ", "1300", "0.00", "",  "0.00"),
]

HEADER = [
    "FlightDate",
    "Reporting_Airline",
    "Tail_Number",
    "Flight_Number_Reporting_Airline",
    "Origin",
    "Dest",
    "CRSDepTime",
    "Cancelled",
    "CancellationCode",
    "Diverted",
]


def main() -> None:
    out_path = Path(__file__).parent / "bts_kjfk_2024_01.csv.zip"

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(HEADER)
    writer.writerows(ROWS)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("On_Time_Reporting_Carrier_2024_1.csv", csv_bytes)

    print(f"wrote {out_path} ({out_path.stat().st_size} bytes, {len(ROWS)} rows)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the fixture**

```bash
cd pipeline
uv run python tests/fixtures/_make_bts_fixture.py
ls -la tests/fixtures/bts_kjfk_2024_01.csv.zip
```

Expected: ZIP file ~500-700 bytes; print confirms 10 rows.

- [ ] **Step 3: Verify ZIP is well-formed**

```bash
unzip -l tests/fixtures/bts_kjfk_2024_01.csv.zip
```

Expected: lists `On_Time_Reporting_Carrier_2024_1.csv` ~700 bytes uncompressed.

- [ ] **Step 4: Commit**

```bash
git add pipeline/tests/fixtures/_make_bts_fixture.py pipeline/tests/fixtures/bts_kjfk_2024_01.csv.zip
git commit -m "test(bts): add BTS fixture generator + 10-row KJFK ZIP"
```

---

## Task 8: Implement `BTSResource` (fixture mode + retries)

**Files:**
- Create: `pipeline/pipeline/resources/bts.py`
- Create: `pipeline/tests/test_bts.py`

- [ ] **Step 1: Write the failing test (fixture mode)**

Create `pipeline/tests/test_bts.py`:

```python
import asyncio
import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pyarrow as pa
import pytest

from pipeline.resources.bts import (
    BTSDownloadError,
    BTSResource,
    extract_csv_from_zip,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bts_kjfk_2024_01.csv.zip"


@pytest.mark.unit
def test_bts_resource_parses_fixture_zip():
    """Fixture mode: download_month returns the fixture ZIP bytes verbatim, no HTTP."""
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=FIXTURE_PATH,
    )

    payload = asyncio.run(resource.download_month(2024, 1))

    assert payload[:2] == b"PK", "Returned bytes must start with ZIP magic"
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        assert any(n.endswith(".csv") for n in zf.namelist())


@pytest.mark.unit
def test_bts_resource_raises_on_missing_fixture(tmp_path):
    """Fixture mode with a path that does not exist raises BTSDownloadError."""
    missing = tmp_path / "nope.zip"
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=missing,
    )

    with pytest.raises(BTSDownloadError, match="fixture not found"):
        asyncio.run(resource.download_month(2024, 1))


@pytest.mark.unit
def test_extract_csv_from_zip_filters_to_airport():
    """extract_csv_from_zip returns only rows where origin OR dest matches IATA."""
    table = extract_csv_from_zip(FIXTURE_PATH.read_bytes(), origin_iata="JFK")

    assert isinstance(table, pa.Table)
    # Fixture has 9 rows touching JFK (rows 1-8 + row 10), 1 LAX-only row dropped:
    assert table.num_rows == 9
    column_names = set(table.column_names)
    assert {
        "flight_date",
        "carrier_iata",
        "origin_iata",
        "destination_iata",
        "cancelled",
        "diverted",
        "year_month",
    }.issubset(column_names), f"missing columns: {column_names}"


@pytest.mark.unit
def test_extract_casts_cancelled_diverted_to_bool():
    """'0.00'/'1.00' string flags are cast to bool."""
    table = extract_csv_from_zip(FIXTURE_PATH.read_bytes(), origin_iata="JFK")

    cancelled = table.column("cancelled").to_pylist()
    diverted = table.column("diverted").to_pylist()

    assert all(isinstance(v, bool) for v in cancelled)
    assert all(isinstance(v, bool) for v in diverted)
    # Fixture: rows with Cancelled='1.00' → True; ours has 3 such rows.
    assert sum(cancelled) == 3
    # Fixture: row 7 has Diverted='1.00'.
    assert sum(diverted) == 1


@pytest.mark.unit
def test_extract_stamps_year_month_partition():
    """All rows for a single download month carry the same year_month partition value."""
    table = extract_csv_from_zip(FIXTURE_PATH.read_bytes(), origin_iata="JFK")

    year_months = set(table.column("year_month").to_pylist())
    assert year_months == {"2024-01"}


@pytest.mark.unit
def test_bts_resource_post_payload_when_no_fixture():
    """Without a fixture, BTSResource POSTs the BTS prezip URL with the right form."""
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=None,
    )

    fake_response = MagicMock()
    fake_response.status = 200
    fake_response.read = AsyncMock(return_value=b"PK\x03\x04fake")
    fake_builder = MagicMock()
    fake_builder.build.return_value.send = AsyncMock(return_value=fake_response)
    fake_client = MagicMock()
    fake_client.get.return_value = fake_builder

    with patch.object(BTSResource, "_client", new_callable=lambda: fake_client):
        payload = asyncio.run(resource.download_month(2024, 1))

    assert payload == b"PK\x03\x04fake"
    fake_client.get.assert_called_once()
    called_url = fake_client.get.call_args.args[0]
    assert "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_1.zip" in called_url
    assert called_url.startswith("https://transtats.bts.gov/PREZIP/")


@pytest.mark.unit
def test_bts_resource_raises_on_404():
    """A 404 from BTS surfaces as BTSDownloadError, not a generic HTTP error."""
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=None,
    )

    fake_response = MagicMock()
    fake_response.status = 404
    fake_response.read = AsyncMock(return_value=b"")
    fake_builder = MagicMock()
    fake_builder.build.return_value.send = AsyncMock(return_value=fake_response)
    fake_client = MagicMock()
    fake_client.get.return_value = fake_builder

    with patch.object(BTSResource, "_client", new_callable=lambda: fake_client):
        with pytest.raises(BTSDownloadError, match="status 404"):
            asyncio.run(resource.download_month(2024, 1))
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd pipeline
uv run pytest tests/test_bts.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'pipeline.resources.bts'`.

- [ ] **Step 3: Implement `BTSResource`**

Create `pipeline/pipeline/resources/bts.py`:

```python
"""BTS On-Time Performance resource.

Downloads monthly ZIPs from the BTS PREZIP endpoint and projects the
columns we care about (flight date, carrier IATA, origin/dest IATA,
cancelled/diverted flags, cancellation code) into a PyArrow table.

Fixture mode (`fixture_file` set) bypasses HTTP entirely and reads the
ZIP from disk. CI uses fixture mode so the test suite never hits BTS.
"""

import io
import zipfile
from datetime import timedelta
from functools import cached_property
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
from pyarrow import csv as pa_csv
from dagster import ConfigurableResource
from pyreqwest.client import Client, ClientBuilder


class BTSDownloadError(RuntimeError):
    """Raised when BTS download fails (network error, missing month, bad fixture)."""


_FILENAME_TEMPLATE = "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"

# BTS columns we project; everything else is dropped at parse time so we don't
# pay deserialization cost for fields we don't use.
_BTS_COLUMNS = [
    "FlightDate",
    "Reporting_Airline",
    "Tail_Number",
    "Flight_Number_Reporting_Airline",
    "Origin",
    "Dest",
    "CRSDepTime",
    "Cancelled",
    "CancellationCode",
    "Diverted",
]

_RENAME_MAP = {
    "FlightDate": "flight_date",
    "Reporting_Airline": "carrier_iata",
    "Tail_Number": "tail_number",
    "Flight_Number_Reporting_Airline": "flight_number",
    "Origin": "origin_iata",
    "Dest": "destination_iata",
    "CRSDepTime": "crs_dep_time",
    "Cancelled": "cancelled",
    "CancellationCode": "cancellation_code",
    "Diverted": "diverted",
}


class BTSResource(ConfigurableResource):
    """Pyreqwest-backed BTS On-Time Performance downloader.

    Set ``fixture_file`` to a Path to skip HTTP and use a local ZIP. Useful
    for unit tests + CI E2E where transtats.bts.gov must not be hit.
    """

    endpoint: str = "https://transtats.bts.gov/PREZIP"
    fixture_file: Path | None = None

    @cached_property
    def _client(self) -> Client:
        return (
            ClientBuilder()
            .connect_timeout(timedelta(seconds=10))
            .timeout(timedelta(seconds=120))
            .build()
        )

    async def download_month(self, year: int, month: int) -> bytes:
        """Return raw BTS ZIP bytes for the given (year, month)."""
        if self.fixture_file is not None:
            if not self.fixture_file.exists():
                raise BTSDownloadError(
                    f"BTS fixture not found at {self.fixture_file} — "
                    "unset BTS_FIXTURE_FILE or point it at a real ZIP"
                )
            return self.fixture_file.read_bytes()

        url = f"{self.endpoint.rstrip('/')}/{_FILENAME_TEMPLATE.format(year=year, month=month)}"
        response = await self._client.get(url).build().send()
        if response.status != 200:
            raise BTSDownloadError(
                f"BTS download for {year}-{month:02d} failed with status {response.status}"
            )
        payload: bytes = await response.read()
        if not payload.startswith(b"PK"):
            raise BTSDownloadError(
                f"BTS response for {year}-{month:02d} is not a ZIP "
                f"(first 16 bytes: {payload[:16]!r})"
            )
        return payload


def _csv_member(zip_bytes: bytes) -> bytes:
    """Return the bytes of the single CSV inside a BTS ZIP."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise BTSDownloadError(f"BTS ZIP has no .csv member: {zf.namelist()}")
        return zf.read(names[0])


def _parse_year_month(table: pa.Table) -> str:
    """Derive 'YYYY-MM' partition value from the first FlightDate row.

    All rows in a BTS monthly download share a year_month, so we read once
    rather than computing per-row.
    """
    flight_dates = table.column("flight_date").to_pylist()
    if not flight_dates:
        return ""
    first = flight_dates[0]  # 'YYYY-MM-DD'
    return first[:7]


def extract_csv_from_zip(zip_bytes: bytes, origin_iata: str) -> pa.Table:
    """Parse a BTS ZIP and return a projected, airport-filtered PyArrow table.

    Returns columns: flight_date, carrier_iata, tail_number, flight_number,
    origin_iata, destination_iata, crs_dep_time, cancelled, cancellation_code,
    diverted, year_month.
    """
    csv_bytes = _csv_member(zip_bytes)

    parse_options = pa_csv.ParseOptions(quote_char='"', escape_char=False)
    convert_options = pa_csv.ConvertOptions(
        include_columns=_BTS_COLUMNS,
        column_types={col: pa.string() for col in _BTS_COLUMNS},
        strings_can_be_null=True,
        null_values=["", "NA"],
    )
    raw = pa_csv.read_csv(
        io.BytesIO(csv_bytes),
        parse_options=parse_options,
        convert_options=convert_options,
    )

    renamed = raw.rename_columns([_RENAME_MAP[c] for c in raw.column_names])

    # Filter to rows where origin OR destination IATA matches the airport.
    mask_origin = pc.equal(renamed.column("origin_iata"), origin_iata)
    mask_dest = pc.equal(renamed.column("destination_iata"), origin_iata)
    filtered = renamed.filter(pc.or_(mask_origin, mask_dest))

    # Cast string flags to bool: '1.00' → True, anything else → False.
    cancelled_bool = pc.equal(filtered.column("cancelled"), "1.00")
    diverted_bool = pc.equal(filtered.column("diverted"), "1.00")
    filtered = filtered.set_column(
        filtered.column_names.index("cancelled"),
        "cancelled",
        cancelled_bool,
    )
    filtered = filtered.set_column(
        filtered.column_names.index("diverted"),
        "diverted",
        diverted_bool,
    )

    # Stamp partition column.
    year_month = _parse_year_month(filtered)
    filtered = filtered.append_column(
        "year_month",
        pa.array([year_month] * filtered.num_rows, type=pa.string()),
    )

    return filtered
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_bts.py -v
```

Expected: all 7 PASS.

- [ ] **Step 5: Lint + format**

```bash
uvx ruff check pipeline/resources/bts.py tests/test_bts.py
uvx ruff format pipeline/resources/bts.py tests/test_bts.py
```

Expected: All checks passed; format already-formatted.

- [ ] **Step 6: Commit**

```bash
git add pipeline/pipeline/resources/bts.py pipeline/tests/test_bts.py
git commit -m "feat(bts): add BTSResource + extract_csv_from_zip with fixture-mode bypass"
```

---

## Task 9: Implement `bts_on_time` Dagster asset

**Files:**
- Create: `pipeline/pipeline/assets/bts_on_time.py`
- Create: `pipeline/tests/test_asset_bts_on_time.py`
- Modify: `pipeline/pipeline/assets/__init__.py` (if exists; otherwise no-op)

- [ ] **Step 1: Write the failing test**

Create `pipeline/tests/test_asset_bts_on_time.py`:

```python
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from pipeline.assets.bts_on_time import bts_on_time
from pipeline.config import PipelineConfig

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bts_kjfk_2024_01.csv.zip"


def _make_config(tmp_path):
    return PipelineConfig.model_validate(
        {
            "airport_icao": "KJFK",
            "ingest_start_date": "2024-01-01",
            "ingest_end_date": "2024-01-08",
            "SEAWEEDFS_S3_ENDPOINT": "http://localhost:8333",
            "seaweedfs_access_key": "admin",
            "seaweedfs_secret_key": "admin",
            "nessie_endpoint": "http://localhost:19120/iceberg/",
            "bts_fixture_file": str(FIXTURE_PATH),
        }
    )


@pytest.mark.unit
def test_bts_on_time_creates_table_and_appends_for_partition(tmp_path):
    """bts_on_time runs for partition '2024-01': filters to KJFK, creates the
    Iceberg table on first run, appends a non-empty PyArrow table.
    """
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    nessie = MagicMock()
    nessie.catalog.table_exists.return_value = False
    appended_tables: list[pa.Table] = []
    nessie.catalog.load_table.return_value.append = lambda t: appended_tables.append(t)

    context = MagicMock()
    context.partition_key = "2024-01"

    bts_on_time(
        context=context,
        pipeline_config=config,
        bts=bts_resource,
        nessie=nessie,
    )

    bts_resource.download_month.assert_called_once_with(2024, 1)
    nessie.catalog.create_namespace_if_not_exists.assert_called_once_with("flights")
    nessie.catalog.create_table.assert_called_once()
    assert len(appended_tables) == 1
    assert appended_tables[0].num_rows == 9  # KJFK rows in fixture


@pytest.mark.unit
def test_bts_on_time_no_op_on_zero_rows(tmp_path):
    """When the airport has no rows in this partition, asset returns without creating
    a table or appending — the empty table must not pollute Iceberg."""
    config = _make_config(tmp_path)

    # Hand back a ZIP that exists but has zero rows after filtering.
    empty_zip_path = tmp_path / "empty.zip"
    import io as _io
    import zipfile as _zip
    with _zip.ZipFile(empty_zip_path, "w", compression=_zip.ZIP_DEFLATED) as zf:
        zf.writestr(
            "empty.csv",
            "FlightDate,Reporting_Airline,Tail_Number,Flight_Number_Reporting_Airline,"
            "Origin,Dest,CRSDepTime,Cancelled,CancellationCode,Diverted\n",
        )

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(empty_zip_path.read_bytes()))

    nessie = MagicMock()
    nessie.catalog.table_exists.return_value = False

    context = MagicMock()
    context.partition_key = "2024-01"

    bts_on_time(
        context=context,
        pipeline_config=config,
        bts=bts_resource,
        nessie=nessie,
    )

    nessie.catalog.create_table.assert_not_called()


@pytest.mark.unit
def test_bts_on_time_does_not_recreate_existing_table(tmp_path):
    """When the table already exists, the asset must not call create_table again."""
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    nessie = MagicMock()
    nessie.catalog.table_exists.return_value = True
    nessie.catalog.load_table.return_value.append = MagicMock()

    context = MagicMock()
    context.partition_key = "2024-01"

    bts_on_time(
        context=context,
        pipeline_config=config,
        bts=bts_resource,
        nessie=nessie,
    )

    nessie.catalog.create_table.assert_not_called()
    nessie.catalog.load_table.return_value.append.assert_called_once()


def _async(value):
    """Return an already-resolved coroutine yielding ``value``."""
    async def _coro():
        return value
    return _coro()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd pipeline
uv run pytest tests/test_asset_bts_on_time.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'pipeline.assets.bts_on_time'`.

- [ ] **Step 3: Implement the asset**

Create `pipeline/pipeline/assets/bts_on_time.py`:

```python
"""BTS On-Time Performance Dagster asset.

Monthly-partitioned: each partition_key is 'YYYY-MM' and lands rows for that
month into Iceberg flights.bts_on_time. Only rows where origin OR destination
matches the configured airport_icao (translated through OurAirports IATA→ICAO
in the staging model) are written to keep the raw table compact.

Schema is created on first run; subsequent partitions append. PyIceberg's
`update_schema` API is used idempotently before append in case the column set
ever evolves (R6 in the spec).
"""

import asyncio

import pyiceberg.schema as sch
from dagster import (
    AssetExecutionContext,
    MonthlyPartitionsDefinition,
    ResourceParam,
    asset,
)
from pyiceberg.types import BooleanType, DateType, NestedField, StringType

from pipeline.config import PipelineConfig
from pipeline.resources.bts import BTSResource, extract_csv_from_zip
from pipeline.resources.nessie import NessieResource

BTS_PARTITIONS = MonthlyPartitionsDefinition(start_date="2024-01-01")

_TABLE_IDENTIFIER = "flights.bts_on_time"

_SCHEMA = sch.Schema(
    NestedField(1, "flight_date", DateType(), required=False),
    NestedField(2, "carrier_iata", StringType(), required=False),
    NestedField(3, "tail_number", StringType(), required=False),
    NestedField(4, "flight_number", StringType(), required=False),
    NestedField(5, "origin_iata", StringType(), required=False),
    NestedField(6, "destination_iata", StringType(), required=False),
    NestedField(7, "crs_dep_time", StringType(), required=False),
    NestedField(8, "cancelled", BooleanType(), required=False),
    NestedField(9, "cancellation_code", StringType(), required=False),
    NestedField(10, "diverted", BooleanType(), required=False),
    NestedField(11, "year_month", StringType(), required=False),
)


def _airport_iata(airport_icao: str) -> str:
    """Phase 1 demo airport is hardcoded to KJFK→JFK; the staging dim_airport
    lookup handles the general case at SQL time. Asset-level filter just
    needs the IATA prefix to keep the raw table small.
    """
    if airport_icao.upper() == "KJFK":
        return "JFK"
    # Fallback: strip the leading 'K' for US airports, otherwise pass through.
    if airport_icao.startswith("K") and len(airport_icao) == 4:
        return airport_icao[1:]
    return airport_icao


@asset(partitions_def=BTS_PARTITIONS)
def bts_on_time(
    context: AssetExecutionContext,
    pipeline_config: ResourceParam[PipelineConfig],
    bts: ResourceParam[BTSResource],
    nessie: ResourceParam[NessieResource],
) -> None:
    year_str, month_str = context.partition_key.split("-")
    year = int(year_str)
    month = int(month_str)

    zip_bytes = asyncio.run(bts.download_month(year, month))

    table = extract_csv_from_zip(
        zip_bytes,
        origin_iata=_airport_iata(pipeline_config.airport_icao),
    )

    if table.num_rows == 0:
        context.log.info(
            f"BTS partition {context.partition_key} produced 0 rows for "
            f"airport {pipeline_config.airport_icao}; skipping append"
        )
        return

    # Cast flight_date string → date32 for Iceberg DateType.
    import pyarrow as pa
    import pyarrow.compute as pc

    flight_date_str = table.column("flight_date")
    flight_date_date = pc.cast(
        pc.strptime(flight_date_str, format="%Y-%m-%d", unit="s"),
        pa.date32(),
    )
    table = table.set_column(
        table.column_names.index("flight_date"),
        "flight_date",
        flight_date_date,
    )

    catalog = nessie.catalog
    catalog.create_namespace_if_not_exists("flights")
    if not catalog.table_exists(_TABLE_IDENTIFIER):
        catalog.create_table(_TABLE_IDENTIFIER, schema=_SCHEMA)

    iceberg_table = catalog.load_table(_TABLE_IDENTIFIER)
    iceberg_table.append(table)

    context.log.info(
        f"Appended {table.num_rows} BTS rows for {context.partition_key} "
        f"to {_TABLE_IDENTIFIER}"
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_asset_bts_on_time.py -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/pipeline/assets/bts_on_time.py pipeline/tests/test_asset_bts_on_time.py
git commit -m "feat(asset): add bts_on_time monthly-partitioned asset"
```

---

## Task 10: Wire `BTSResource` + `bts_on_time` into Dagster `Definitions`

**Files:**
- Modify: `pipeline/pipeline/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `pipeline/tests/test_definitions_bts_wired.py`:

```python
import pytest


@pytest.mark.unit
def test_bts_on_time_asset_registered():
    """The bts_on_time asset must be in the Definitions assets list."""
    from pipeline import defs

    asset_keys = {a.key.to_user_string() for a in defs.assets}  # type: ignore[attr-defined]
    assert "bts_on_time" in asset_keys, (
        f"bts_on_time missing from Definitions; have {asset_keys}"
    )


@pytest.mark.unit
def test_bts_resource_registered_when_env_present(monkeypatch):
    """When env vars are present, defs.resources contains a 'bts' resource."""
    monkeypatch.setenv("AIRPORT_ICAO", "KJFK")
    monkeypatch.setenv("INGEST_START_DATE", "2024-01-01")
    monkeypatch.setenv("INGEST_END_DATE", "2024-01-08")
    monkeypatch.setenv("SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("SEAWEEDFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("SEAWEEDFS_SECRET_KEY", "admin")
    monkeypatch.setenv("NESSIE_ENDPOINT", "http://localhost:19120/iceberg/")

    # Reload module so resources rebuild against fresh env.
    import importlib

    import pipeline

    importlib.reload(pipeline)

    assert "bts" in pipeline.defs.resources  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd pipeline
uv run pytest tests/test_definitions_bts_wired.py -v
```

Expected: both tests FAIL — first with `KeyError`/no asset; second with `assert 'bts' in ...`.

- [ ] **Step 3: Edit `pipeline/pipeline/__init__.py`**

Replace contents with:

```python
import os

from dagster import Definitions, ResourceDefinition
from pydantic import ValidationError

from pipeline.assets.bts_on_time import bts_on_time
from pipeline.assets.frontend_exports import frontend_exports
from pipeline.assets.raw_flights import raw_flights
from pipeline.assets.transformed_flights import transformed_flights
from pipeline.config import PipelineConfig
from pipeline.resources.bts import BTSResource
from pipeline.resources.nessie import NessieResource
from pipeline.resources.opensky import OpenSkyResource
from pipeline.resources.seaweedfs import SeaweedFSResource


def _make_resources() -> dict[str, ResourceDefinition]:
    cfg = PipelineConfig.from_env()
    opensky = OpenSkyResource(
        client_id=cfg.opensky_client_id,
        client_secret=cfg.opensky_client_secret,
    )
    bts = BTSResource(
        endpoint=cfg.bts_endpoint,
        fixture_file=cfg.bts_fixture_file,
    )
    return {
        "pipeline_config": ResourceDefinition.hardcoded_resource(cfg),
        "opensky": ResourceDefinition.hardcoded_resource(opensky),
        "bts": ResourceDefinition.hardcoded_resource(bts),
        "seaweedfs": ResourceDefinition.hardcoded_resource(
            SeaweedFSResource(
                endpoint=cfg.seaweedfs_endpoint,
                access_key=cfg.seaweedfs_access_key,
                secret_key=cfg.seaweedfs_secret_key,
            )
        ),
        "nessie": ResourceDefinition.hardcoded_resource(
            NessieResource(
                endpoint=cfg.nessie_endpoint,
                s3_endpoint=cfg.seaweedfs_endpoint,
                s3_access_key=cfg.seaweedfs_access_key,
                s3_secret_key=cfg.seaweedfs_secret_key,
            )
        ),
    }


def _resources_or_empty() -> dict[str, ResourceDefinition]:
    try:
        return _make_resources()
    except (KeyError, ValidationError):
        if os.environ.get("DAGSTER_ENV") == "prod":
            raise
        return {}


defs = Definitions(
    assets=[raw_flights, bts_on_time, transformed_flights, frontend_exports],
    resources=_resources_or_empty(),
)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_definitions_bts_wired.py -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/pipeline/__init__.py pipeline/tests/test_definitions_bts_wired.py
git commit -m "feat(dagster): wire BTSResource + bts_on_time into Definitions"
```

---

## Task 11: Make `transformed_flights` depend on `bts_on_time`

**Files:**
- Modify: `pipeline/pipeline/assets/transformed_flights.py`
- Modify: `pipeline/tests/test_asset_transformed_flights.py`

- [ ] **Step 1: Write the failing test**

Append to `pipeline/tests/test_asset_transformed_flights.py`:

```python
def test_transformed_flights_depends_on_bts_on_time():
    """transformed_flights must declare an AssetIn for bts_on_time so dbt build
    waits for the BTS partition to land before executing.
    """
    from dagster import AssetKey

    from pipeline.assets.transformed_flights import transformed_flights as asset_fn

    asset_def = asset_fn.op  # dagster wraps assets as ops
    input_keys = {inp.dagster_type_key for inp in asset_def.input_defs}
    deps = {ak.to_user_string() for ak in asset_fn.dependency_keys}
    assert "bts_on_time" in deps, (
        f"transformed_flights deps missing bts_on_time; have {deps}"
    )
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd pipeline
uv run pytest tests/test_asset_transformed_flights.py::test_transformed_flights_depends_on_bts_on_time -v
```

Expected: FAIL — `assert 'bts_on_time' in {'raw_flights'}`.

- [ ] **Step 3: Edit `pipeline/pipeline/assets/transformed_flights.py`**

Replace contents with:

```python
import subprocess
from pathlib import Path

import pyarrow as pa
from dagster import AssetIn, Nothing, ResourceParam, asset

from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent / "transforms"


@asset(ins={"bts_on_time": AssetIn(dagster_type=Nothing)})
def transformed_flights(
    pipeline_config: ResourceParam[PipelineConfig],
    raw_flights: pa.Table,
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None:
    result = subprocess.run(
        [
            "dbt",
            "run",
            "--project-dir",
            str(DBT_PROJECT_DIR),
            "--profiles-dir",
            str(DBT_PROJECT_DIR),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt run failed:\n{result.stdout}\n{result.stderr}")
```

- [ ] **Step 4: Run test to verify pass**

```bash
uv run pytest tests/test_asset_transformed_flights.py::test_transformed_flights_depends_on_bts_on_time -v
```

Expected: PASS.

- [ ] **Step 5: Make dbt run also seed**

In the same file, change the subprocess call so seeds are loaded before models:

```python
import subprocess
from pathlib import Path

import pyarrow as pa
from dagster import AssetIn, Nothing, ResourceParam, asset

from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent / "transforms"


def _run_dbt(subcommand: str) -> None:
    result = subprocess.run(
        [
            "dbt",
            subcommand,
            "--project-dir",
            str(DBT_PROJECT_DIR),
            "--profiles-dir",
            str(DBT_PROJECT_DIR),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt {subcommand} failed:\n{result.stdout}\n{result.stderr}")


@asset(ins={"bts_on_time": AssetIn(dagster_type=Nothing)})
def transformed_flights(
    pipeline_config: ResourceParam[PipelineConfig],
    raw_flights: pa.Table,
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None:
    _run_dbt("seed")
    _run_dbt("run")
```

- [ ] **Step 6: Run all transformed_flights tests**

```bash
uv run pytest tests/test_asset_transformed_flights.py -v
```

Expected: all PASS. Existing tests check `mock_run.assert_called_once()` — that needs adjusting:

Open `pipeline/tests/test_asset_transformed_flights.py` and find:

```python
mock_run.assert_called_once()
cmd = mock_run.call_args.args[0]
```

Replace with:

```python
assert mock_run.call_count == 2
seed_call, run_call = mock_run.call_args_list
assert seed_call.args[0][1] == "seed"
assert run_call.args[0][1] == "run"
cmd = run_call.args[0]
```

- [ ] **Step 7: Run again**

```bash
uv run pytest tests/test_asset_transformed_flights.py -v
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add pipeline/pipeline/assets/transformed_flights.py pipeline/tests/test_asset_transformed_flights.py
git commit -m "feat(asset): chain transformed_flights after bts_on_time + run dbt seed"
```

---

## Task 12: Add `stg_bts_on_time` staging model

**Files:**
- Create: `pipeline/transforms/models/staging/stg_bts_on_time.sql`
- Modify: `pipeline/transforms/models/staging/schema.yml`
- Modify: `pipeline/tests/test_dbt_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `pipeline/tests/test_dbt_models.py`:

```python
@pytest.mark.unit
def test_stg_bts_on_time_inner_joins_dim_airport_and_dim_carrier() -> None:
    """stg_bts_on_time.sql must inner-join dim_airport (origin + dest) and dim_carrier."""
    sql = (STAGING_DIR / "stg_bts_on_time.sql").read_text()
    assert "INNER JOIN {{ ref('dim_airport') }}" in sql
    assert sql.count("INNER JOIN {{ ref('dim_airport') }}") == 2, (
        "stg_bts_on_time must INNER JOIN dim_airport twice (origin + dest)"
    )
    assert "INNER JOIN {{ ref('dim_carrier') }}" in sql


@pytest.mark.unit
def test_stg_bts_on_time_filters_empty_iata_codes() -> None:
    """stg_bts_on_time must filter rows with empty IATA codes via NULLIF."""
    sql = (STAGING_DIR / "stg_bts_on_time.sql").read_text()
    for col in ("origin_iata", "destination_iata", "carrier_iata"):
        assert f"NULLIF(b.{col}, '') IS NOT NULL" in sql, (
            f"stg_bts_on_time must filter empty {col} via NULLIF"
        )


@pytest.mark.unit
def test_stg_bts_on_time_carries_carrier_name_through() -> None:
    """stg_bts_on_time aliases dim_carrier.name as carrier_name so marts don't re-join."""
    sql = (STAGING_DIR / "stg_bts_on_time.sql").read_text()
    assert "c.name" in sql and "AS carrier_name" in sql
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd pipeline
uv run pytest tests/test_dbt_models.py -k "stg_bts" -v
```

Expected: 3 FAILS — files don't exist.

- [ ] **Step 3: Create `pipeline/transforms/models/staging/stg_bts_on_time.sql`**

```sql
SELECT
    b.flight_date,
    a_origin.icao   AS origin_icao,
    a_dest.icao     AS destination_icao,
    c.icao          AS carrier_icao,
    c.name          AS carrier_name,
    b.carrier_iata,
    b.flight_number,
    b.tail_number,
    b.cancelled,
    b.cancellation_code,
    b.diverted,
    b.year_month
FROM nessie.flights.bts_on_time AS b
INNER JOIN {{ ref('dim_airport') }} AS a_origin
    ON a_origin.iata = b.origin_iata
INNER JOIN {{ ref('dim_airport') }} AS a_dest
    ON a_dest.iata = b.destination_iata
INNER JOIN {{ ref('dim_carrier') }} AS c
    ON c.iata = b.carrier_iata
WHERE NULLIF(b.origin_iata, '') IS NOT NULL
  AND NULLIF(b.destination_iata, '') IS NOT NULL
  AND NULLIF(b.carrier_iata, '') IS NOT NULL
```

- [ ] **Step 4: Update `pipeline/transforms/models/staging/schema.yml`**

Replace contents with:

```yaml
version: 2

models:
  - name: stg_flights
    description: >
      Cleaned and cast OpenSky flight records read directly from Iceberg
      parquet data files on S3.
    columns:
      - name: icao24
        description: 24-bit ICAO aircraft address (hex string)
        tests:
          - not_null
      - name: callsign
        description: Flight callsign (trimmed)
        tests:
          - not_null
      - name: departed_at
        description: Departure timestamp cast from first_seen epoch
        tests:
          - not_null
      - name: arrived_at
        description: Arrival timestamp cast from last_seen epoch
      - name: origin_icao
        description: Estimated departure airport ICAO code
      - name: destination_icao
        description: Estimated arrival airport ICAO code

  - name: stg_bts_on_time
    description: >
      BTS On-Time Performance flights with IATA codes translated to ICAO via
      dim_airport and dim_carrier. Inner joins drop unmappable rows; coverage
      monitored via the not-null tests below.
    columns:
      - name: flight_date
        tests:
          - not_null
      - name: origin_icao
        tests:
          - not_null
      - name: destination_icao
        tests:
          - not_null
      - name: carrier_icao
        tests:
          - not_null
      - name: cancelled
        tests:
          - not_null
```

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest tests/test_dbt_models.py -k "stg_bts" -v
```

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/transforms/models/staging/stg_bts_on_time.sql pipeline/transforms/models/staging/schema.yml pipeline/tests/test_dbt_models.py
git commit -m "feat(dbt): add stg_bts_on_time + schema not-null tests on key cols"
```

---

## Task 13: Add cancellation marts

**Files:**
- Create: `pipeline/transforms/models/marts/agg_carrier_cancellations.sql`
- Create: `pipeline/transforms/models/marts/agg_route_cancellations.sql`
- Modify: `pipeline/tests/test_dbt_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `pipeline/tests/test_dbt_models.py`:

```python
@pytest.mark.unit
@pytest.mark.parametrize(
    "mart", ["agg_carrier_cancellations", "agg_route_cancellations"]
)
def test_cancellation_marts_use_external_parquet_with_correct_location(mart: str) -> None:
    """Each cancellation mart must declare an s3:// location for external parquet."""
    sql = (MARTS_DIR / f"{mart}.sql").read_text()
    assert "config(" in sql and "location=" in sql
    assert "s3://" in sql and "warehouse/marts/" in sql
    assert mart in sql, f"{mart}.sql must reference its own name in the location"


@pytest.mark.unit
@pytest.mark.parametrize(
    "mart,required",
    [
        (
            "agg_carrier_cancellations",
            (
                "origin_icao",
                "carrier_icao",
                "carrier_name",
                "total_scheduled",
                "cancelled",
                "cancellation_rate",
                "period_start",
                "period_end",
            ),
        ),
        (
            "agg_route_cancellations",
            (
                "origin_icao",
                "destination_icao",
                "total_scheduled",
                "cancelled",
                "cancellation_rate",
                "period_start",
                "period_end",
            ),
        ),
    ],
)
def test_cancellation_marts_have_required_columns(mart: str, required: tuple[str, ...]) -> None:
    sql = (MARTS_DIR / f"{mart}.sql").read_text()
    for col in required:
        # Either bare column reference (origin_icao) or "AS col" alias
        assert col in sql, f"{mart}.sql missing required column {col}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "mart", ["agg_carrier_cancellations", "agg_route_cancellations"]
)
def test_cancellation_rate_uses_nullif_count_pattern(mart: str) -> None:
    """NULLIF(COUNT(*), 0) guards against empty-group division."""
    sql = (MARTS_DIR / f"{mart}.sql").read_text()
    assert "NULLIF(COUNT(*), 0)" in sql, (
        f"{mart}.sql must use NULLIF(COUNT(*), 0) for the cancellation_rate denom"
    )
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd pipeline
uv run pytest tests/test_dbt_models.py -k "cancellation_marts or cancellation_rate" -v
```

Expected: parametrised FAILS — files don't exist.

- [ ] **Step 3: Create `pipeline/transforms/models/marts/agg_carrier_cancellations.sql`**

```sql
{{ config(
    location="s3://" ~ env_var('RAW_BUCKET', 'raw-flights') ~ "/warehouse/marts/" ~ this.name ~ ".parquet"
) }}
SELECT
    origin_icao,
    carrier_icao,
    MAX(carrier_name)                                              AS carrier_name,
    COUNT(*)                                                       AS total_scheduled,
    SUM(CASE WHEN cancelled THEN 1 ELSE 0 END)                     AS cancelled,
    ROUND(
        SUM(CASE WHEN cancelled THEN 1 ELSE 0 END) * 1.0
            / NULLIF(COUNT(*), 0),
        4
    )                                                              AS cancellation_rate,
    MIN(flight_date)                                               AS period_start,
    MAX(flight_date)                                               AS period_end
FROM {{ ref('stg_bts_on_time') }}
GROUP BY origin_icao, carrier_icao
```

- [ ] **Step 4: Create `pipeline/transforms/models/marts/agg_route_cancellations.sql`**

```sql
{{ config(
    location="s3://" ~ env_var('RAW_BUCKET', 'raw-flights') ~ "/warehouse/marts/" ~ this.name ~ ".parquet"
) }}
SELECT
    origin_icao,
    destination_icao,
    COUNT(*)                                                       AS total_scheduled,
    SUM(CASE WHEN cancelled THEN 1 ELSE 0 END)                     AS cancelled,
    ROUND(
        SUM(CASE WHEN cancelled THEN 1 ELSE 0 END) * 1.0
            / NULLIF(COUNT(*), 0),
        4
    )                                                              AS cancellation_rate,
    MIN(flight_date)                                               AS period_start,
    MAX(flight_date)                                               AS period_end
FROM {{ ref('stg_bts_on_time') }}
GROUP BY origin_icao, destination_icao
```

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest tests/test_dbt_models.py -k "cancellation_marts or cancellation_rate" -v
```

Expected: 6 PASS (3 parametrised tests × 2 marts; column-list test is 2 cases not 3).

- [ ] **Step 6: Commit**

```bash
git add pipeline/transforms/models/marts/agg_carrier_cancellations.sql pipeline/transforms/models/marts/agg_route_cancellations.sql pipeline/tests/test_dbt_models.py
git commit -m "feat(dbt): add agg_carrier_cancellations + agg_route_cancellations marts"
```

---

## Task 14: Wire cancellation marts into `frontend_exports`

**Files:**
- Modify: `pipeline/pipeline/assets/frontend_exports.py`
- Modify: `pipeline/tests/test_asset_transformed_flights.py`

- [ ] **Step 1: Write the failing test**

Append to `pipeline/tests/test_asset_transformed_flights.py`:

```python
AGG_CARRIER_CANC = pa.table(
    {
        "origin_icao": ["KJFK"],
        "carrier_icao": ["AAL"],
        "carrier_name": ["American Airlines"],
        "total_scheduled": [1000],
        "cancelled": [50],
        "cancellation_rate": [0.05],
        "period_start": pa.array([date(2024, 1, 1)], type=pa.date32()),
        "period_end": pa.array([date(2024, 12, 31)], type=pa.date32()),
    }
)

AGG_ROUTE_CANC = pa.table(
    {
        "origin_icao": ["KJFK"],
        "destination_icao": ["KLAX"],
        "total_scheduled": [800],
        "cancelled": [40],
        "cancellation_rate": [0.05],
        "period_start": pa.array([date(2024, 1, 1)], type=pa.date32()),
        "period_end": pa.array([date(2024, 12, 31)], type=pa.date32()),
    }
)


def test_frontend_exports_includes_cancellation_marts():
    """frontend_exports must read both cancellation marts and upload them under
    the airport-namespaced keys carrier_cancellations.parquet + route_cancellations.parquet.
    """
    config = _make_config()
    mock_seaweedfs = MagicMock()
    mock_con = MagicMock()
    mock_con.__enter__ = lambda s: mock_con
    mock_con.__exit__ = MagicMock(return_value=False)
    mock_con.execute.side_effect = [MagicMock() for _ in range(7)] + [
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_DAILY_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_CARRIER_CANC),
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_CANC),
    ]

    with patch("pipeline.assets.frontend_exports.duckdb.connect", return_value=mock_con):
        frontend_exports(pipeline_config=config, seaweedfs=mock_seaweedfs)

    keys = [c.kwargs["key"] for c in mock_seaweedfs.upload_parquet.call_args_list]
    assert "KJFK/carrier_cancellations.parquet" in keys
    assert "KJFK/route_cancellations.parquet" in keys

    # Validate the read SQL for cancellation marts uses origin_icao predicate.
    read_calls = [c for c in mock_con.execute.call_args_list if "read_parquet" in c.args[0]]
    carrier_call = next(c for c in read_calls if "agg_carrier_cancellations" in c.args[0])
    route_canc_call = next(c for c in read_calls if "agg_route_cancellations" in c.args[0])
    assert "WHERE origin_icao = $airport" in carrier_call.args[0]
    assert "WHERE origin_icao = $airport OR destination_icao = $airport" in route_canc_call.args[0]
    assert carrier_call.args[1] == {"airport": "KJFK"}
    assert route_canc_call.args[1] == {"airport": "KJFK"}
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd pipeline
uv run pytest tests/test_asset_transformed_flights.py::test_frontend_exports_includes_cancellation_marts -v
```

Expected: FAIL — keys missing or KeyError on `_MART_AIRPORT_PREDICATE`.

- [ ] **Step 3: Edit `pipeline/pipeline/assets/frontend_exports.py`**

Replace `_MARTS`, `_EXPORT_KEYS`, `_MART_AIRPORT_PREDICATE` blocks with:

```python
_MARTS = (
    "agg_route_timeliness",
    "agg_daily_timeliness",
    "agg_carrier_cancellations",
    "agg_route_cancellations",
)
_EXPORT_KEYS = {
    "agg_route_timeliness": "route_timeliness.parquet",
    "agg_daily_timeliness": "daily_timeliness.parquet",
    "agg_carrier_cancellations": "carrier_cancellations.parquet",
    "agg_route_cancellations": "route_cancellations.parquet",
}
# Marts are airport-agnostic; export keys namespace by airport, so each file
# must only contain rows that pertain to that airport.
#
# - agg_route_timeliness / agg_route_cancellations have origin + destination,
#   "route through KJFK" can flow either way → filter on either.
# - agg_daily_timeliness groups by (date, origin_icao) only.
# - agg_carrier_cancellations groups by (origin_icao, carrier_icao) only.
_MART_AIRPORT_PREDICATE = {
    "agg_route_timeliness": "origin_icao = $airport OR destination_icao = $airport",
    "agg_daily_timeliness": "origin_icao = $airport",
    "agg_carrier_cancellations": "origin_icao = $airport",
    "agg_route_cancellations": "origin_icao = $airport OR destination_icao = $airport",
}
```

- [ ] **Step 4: Update existing fixture call list to expect 4 reads**

Find the test `test_frontend_exports_reads_marts_from_s3` in
`pipeline/tests/test_asset_transformed_flights.py`. Update `mock_con.execute.side_effect`:

```python
    mock_con.execute.side_effect = [
        MagicMock(),  # INSTALL httpfs
        MagicMock(),  # LOAD httpfs
        MagicMock(),  # SET s3_endpoint
        MagicMock(),  # SET s3_access_key_id
        MagicMock(),  # SET s3_secret_access_key
        MagicMock(),  # SET s3_use_ssl
        MagicMock(),  # SET s3_url_style
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_DAILY_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_CARRIER_CANC),
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_CANC),
    ]
```

And the upload assertion `assert mock_seaweedfs.upload_parquet.call_count == 2` becomes:

```python
    assert mock_seaweedfs.upload_parquet.call_count == 4
```

Same applies to `test_frontend_exports_strips_scheme_from_endpoint` (4 reads instead of 2 plus 7 setup).

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest tests/test_asset_transformed_flights.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/pipeline/assets/frontend_exports.py pipeline/tests/test_asset_transformed_flights.py
git commit -m "feat(exports): export cancellation marts as airport-filtered parquets"
```

---

## Task 15: Generate stub Parquet fixtures for E2E

**Files:**
- Create: `pipeline/tests/fixtures/_make_cancellation_parquets.py`
- Create: `pipeline/tests/fixtures/carrier_cancellations.parquet`
- Create: `pipeline/tests/fixtures/route_cancellations.parquet`

- [ ] **Step 1: Write the generator**

Create `pipeline/tests/fixtures/_make_cancellation_parquets.py`:

```python
"""Generate stub cancellation Parquet fixtures for the frontend E2E smoke test.

CI E2E uploads these to SeaweedFS via the frontend_exports stub path so the
browser smoke test renders both Highcharts bars without running the whole BTS
pipeline. Re-run after schema changes; commit the resulting Parquet files.
"""

from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

OUT_DIR = Path(__file__).parent

CARRIER = pa.table(
    {
        "origin_icao": ["KJFK"] * 4,
        "carrier_icao": ["AAL", "DAL", "UAL", "JBU"],
        "carrier_name": [
            "American Airlines",
            "Delta Air Lines",
            "United Airlines",
            "JetBlue Airways",
        ],
        "total_scheduled": [1000, 900, 800, 700],
        "cancelled": [50, 27, 16, 14],
        "cancellation_rate": [0.05, 0.03, 0.02, 0.02],
        "period_start": pa.array([date(2024, 1, 1)] * 4, type=pa.date32()),
        "period_end": pa.array([date(2024, 12, 31)] * 4, type=pa.date32()),
    }
)

ROUTE = pa.table(
    {
        "origin_icao": ["KJFK"] * 5,
        "destination_icao": ["KLAX", "KORD", "KMIA", "KATL", "KSEA"],
        "total_scheduled": [400, 350, 300, 280, 250],
        "cancelled": [20, 14, 9, 8, 5],
        "cancellation_rate": [0.05, 0.04, 0.03, 0.029, 0.02],
        "period_start": pa.array([date(2024, 1, 1)] * 5, type=pa.date32()),
        "period_end": pa.array([date(2024, 12, 31)] * 5, type=pa.date32()),
    }
)


def main() -> None:
    pq.write_table(CARRIER, OUT_DIR / "carrier_cancellations.parquet")
    pq.write_table(ROUTE, OUT_DIR / "route_cancellations.parquet")
    print(f"wrote carrier ({CARRIER.num_rows} rows) + route ({ROUTE.num_rows} rows) parquets")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate**

```bash
cd pipeline
uv run python tests/fixtures/_make_cancellation_parquets.py
ls -la tests/fixtures/{carrier,route}_cancellations.parquet
```

Expected: each file ~1-2 KB.

- [ ] **Step 3: Sanity-check via DuckDB**

```bash
duckdb -c "SELECT * FROM read_parquet('pipeline/tests/fixtures/carrier_cancellations.parquet');"
```

Expected: 4 rows with American/Delta/United/JetBlue.

- [ ] **Step 4: Commit**

```bash
git add pipeline/tests/fixtures/_make_cancellation_parquets.py \
        pipeline/tests/fixtures/carrier_cancellations.parquet \
        pipeline/tests/fixtures/route_cancellations.parquet
git commit -m "test(fixtures): add cancellation Parquet stubs for E2E smoke"
```

---

## Task 16: Add frontend queries + types for cancellation marts

**Files:**
- Modify: `frontend/src/db/queries.ts`

- [ ] **Step 1: Append to `frontend/src/db/queries.ts`**

Open the file. After the existing `queryDailyTimeliness` function, append:

```typescript
export interface CarrierCancellation {
  origin_icao: string
  carrier_icao: string
  carrier_name: string
  total_scheduled: number
  cancelled: number
  cancellation_rate: number
  period_start: number | string | Date
  period_end: number | string | Date
}

export interface RouteCancellation {
  origin_icao: string
  destination_icao: string
  total_scheduled: number
  cancelled: number
  cancellation_rate: number
  period_start: number | string | Date
  period_end: number | string | Date
}

export async function queryCarrierCancellations(
  airportIcao: string
): Promise<CarrierCancellation[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
    const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/carrier_cancellations.parquet`
    const result = await conn.query(
      `SELECT * FROM read_parquet('${url}') ORDER BY cancellation_rate DESC`
    )
    return result.toArray().map((r) => r.toJSON() as CarrierCancellation)
  } finally {
    await conn.close()
  }
}

export async function queryRouteCancellations(
  airportIcao: string
): Promise<RouteCancellation[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
    const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/route_cancellations.parquet`
    const result = await conn.query(
      `SELECT * FROM read_parquet('${url}') ORDER BY cancellation_rate DESC`
    )
    return result.toArray().map((r) => r.toJSON() as RouteCancellation)
  } finally {
    await conn.close()
  }
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/db/queries.ts
git commit -m "feat(frontend): add queryCarrierCancellations + queryRouteCancellations"
```

---

## Task 17: Implement `<CancellationSection>` + chart wrappers + tests

**Files:**
- Create: `frontend/src/components/CancellationSection/CancellationSection.tsx`
- Create: `frontend/src/components/CancellationSection/CarrierBar.tsx`
- Create: `frontend/src/components/CancellationSection/RouteBar.tsx`
- Create: `frontend/src/components/CancellationSection/CancellationSection.css`
- Create: `frontend/src/components/CancellationSection/CancellationSection.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/CancellationSection/CancellationSection.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CancellationSection from './CancellationSection'
import {
  queryCarrierCancellations,
  queryRouteCancellations,
} from '../../db/queries'

vi.mock('../../db/queries', () => ({
  queryCarrierCancellations: vi.fn(),
  queryRouteCancellations: vi.fn(),
}))

vi.mock('highcharts-react-official', () => ({
  default: ({ options }: { options: Highcharts.Options }) => (
    <div
      data-testid={`hc-${(options.title?.text ?? 'untitled').toLowerCase().replace(/\s+/g, '-')}`}
    >
      {JSON.stringify(options.series?.[0]?.data ?? [])}
    </div>
  ),
}))

const mockCarrier = vi.mocked(queryCarrierCancellations)
const mockRoute = vi.mocked(queryRouteCancellations)

describe('CancellationSection', () => {
  beforeEach(() => {
    mockCarrier.mockReset()
    mockRoute.mockReset()
  })

  it('shows loading state while queries pending', () => {
    mockCarrier.mockReturnValue(new Promise(() => {}))
    mockRoute.mockReturnValue(new Promise(() => {}))
    render(<CancellationSection airportIcao="KJFK" />)
    expect(screen.getByText(/loading cancellation/i)).toBeInTheDocument()
    expect(screen.getByText(/loading/i)).toHaveAttribute('aria-busy', 'true')
  })

  it('shows empty state when no rows', async () => {
    mockCarrier.mockResolvedValue([])
    mockRoute.mockResolvedValue([])
    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() =>
      expect(screen.getByText(/no cancellation data/i)).toBeInTheDocument()
    )
  })

  it('shows error on rejected query', async () => {
    mockCarrier.mockRejectedValue(new Error('boom'))
    mockRoute.mockResolvedValue([])
    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/failed to load/i)
    )
  })

  it('renders carrier bar with top 10 sorted by rate desc', async () => {
    const carriers = Array.from({ length: 15 }, (_, i) => ({
      origin_icao: 'KJFK',
      carrier_icao: `C${i.toString().padStart(2, '0')}`,
      carrier_name: `Carrier ${i}`,
      total_scheduled: 1000,
      cancelled: 100 - i,
      cancellation_rate: (100 - i) / 1000,
      period_start: '2024-01-01',
      period_end: '2024-12-31',
    }))
    mockCarrier.mockResolvedValue(carriers)
    mockRoute.mockResolvedValue([])

    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() => expect(screen.getByTestId(/hc-carriers/)).toBeInTheDocument())

    const carrierEl = screen.getByTestId(/hc-carriers/)
    const data = JSON.parse(carrierEl.textContent ?? '[]') as Array<{ name: string }>
    expect(data).toHaveLength(10)
    expect(data[0].name).toBe('Carrier 0')
  })

  it('renders route bar with top 10 sorted by rate desc', async () => {
    mockCarrier.mockResolvedValue([])
    const routes = Array.from({ length: 12 }, (_, i) => ({
      origin_icao: 'KJFK',
      destination_icao: `KX${i.toString().padStart(2, '0')}`,
      total_scheduled: 500,
      cancelled: 50 - i,
      cancellation_rate: (50 - i) / 500,
      period_start: '2024-01-01',
      period_end: '2024-12-31',
    }))
    mockRoute.mockResolvedValue(routes)

    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() => expect(screen.getByTestId(/hc-routes/)).toBeInTheDocument())

    const routeEl = screen.getByTestId(/hc-routes/)
    const data = JSON.parse(routeEl.textContent ?? '[]') as Array<{ name: string }>
    expect(data).toHaveLength(10)
    expect(data[0].name).toBe('KJFK → KX00')
  })

  it('formats rate as percent in carrier bar data', async () => {
    mockCarrier.mockResolvedValue([
      {
        origin_icao: 'KJFK',
        carrier_icao: 'AAL',
        carrier_name: 'American Airlines',
        total_scheduled: 1000,
        cancelled: 12,
        cancellation_rate: 0.0123,
        period_start: '2024-01-01',
        period_end: '2024-12-31',
      },
    ])
    mockRoute.mockResolvedValue([])

    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() => expect(screen.getByTestId(/hc-carriers/)).toBeInTheDocument())

    const data = JSON.parse(
      screen.getByTestId(/hc-carriers/).textContent ?? '[]'
    ) as Array<{ y: number }>
    // Highcharts wants percentage units → 1.23
    expect(data[0].y).toBeCloseTo(1.23, 2)
  })
})
```

- [ ] **Step 2: Create the bar wrapper components**

`frontend/src/components/CancellationSection/CarrierBar.tsx`:

```tsx
import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { CarrierCancellation } from '../../db/queries'

interface Props {
  airportIcao: string
  carriers: readonly CarrierCancellation[]
}

export default function CarrierBar({ airportIcao, carriers }: Props) {
  const data = carriers
    .slice()
    .sort((a, b) => b.cancellation_rate - a.cancellation_rate)
    .slice(0, 10)
    .map(c => ({
      name: c.carrier_name,
      y: c.cancellation_rate * 100,
      total: c.total_scheduled,
      cancelled: c.cancelled,
    }))

  const options: Highcharts.Options = {
    chart: { type: 'bar', backgroundColor: 'transparent', height: 360 },
    title: { text: `Carriers — ${airportIcao}` },
    xAxis: {
      categories: data.map(d => d.name),
      labels: { style: { color: 'currentColor' } },
    },
    yAxis: {
      title: { text: 'Cancellation rate (%)' },
      labels: { style: { color: 'currentColor' } },
    },
    legend: { enabled: false },
    credits: { enabled: false },
    tooltip: {
      pointFormat:
        '<b>{point.y:.2f}%</b><br/>{point.cancelled:,} of {point.total:,} cancelled',
    },
    series: [
      {
        type: 'bar',
        name: 'Cancellation rate',
        data,
        colorByPoint: false,
        color: 'oklch(56% 0.19 25)',
      },
    ],
  }

  return <HighchartsReact highcharts={Highcharts} options={options} />
}
```

`frontend/src/components/CancellationSection/RouteBar.tsx`:

```tsx
import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { RouteCancellation } from '../../db/queries'

interface Props {
  airportIcao: string
  routes: readonly RouteCancellation[]
}

export default function RouteBar({ airportIcao, routes }: Props) {
  const data = routes
    .slice()
    .sort((a, b) => b.cancellation_rate - a.cancellation_rate)
    .slice(0, 10)
    .map(r => ({
      name: `${r.origin_icao} → ${r.destination_icao}`,
      y: r.cancellation_rate * 100,
      total: r.total_scheduled,
      cancelled: r.cancelled,
    }))

  const options: Highcharts.Options = {
    chart: { type: 'bar', backgroundColor: 'transparent', height: 360 },
    title: { text: `Routes — ${airportIcao}` },
    xAxis: {
      categories: data.map(d => d.name),
      labels: { style: { color: 'currentColor' } },
    },
    yAxis: {
      title: { text: 'Cancellation rate (%)' },
      labels: { style: { color: 'currentColor' } },
    },
    legend: { enabled: false },
    credits: { enabled: false },
    tooltip: {
      pointFormat:
        '<b>{point.y:.2f}%</b><br/>{point.cancelled:,} of {point.total:,} cancelled',
    },
    series: [
      {
        type: 'bar',
        name: 'Cancellation rate',
        data,
        color: 'oklch(56% 0.19 25)',
      },
    ],
  }

  return <HighchartsReact highcharts={Highcharts} options={options} />
}
```

- [ ] **Step 3: Create the section component**

`frontend/src/components/CancellationSection/CancellationSection.tsx`:

```tsx
import { useEffect, useState } from 'react'
import {
  CarrierCancellation,
  RouteCancellation,
  queryCarrierCancellations,
  queryRouteCancellations,
} from '../../db/queries'
import { fmtDate } from '../../db/format'
import CarrierBar from './CarrierBar'
import RouteBar from './RouteBar'
import './CancellationSection.css'

interface Props {
  airportIcao: string
}

interface Data {
  carriers: CarrierCancellation[]
  routes: RouteCancellation[]
}

export default function CancellationSection({ airportIcao }: Props) {
  const [data, setData] = useState<Data | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    Promise.all([
      queryCarrierCancellations(airportIcao),
      queryRouteCancellations(airportIcao),
    ])
      .then(([carriers, routes]) => {
        if (isMounted) setData({ carriers, routes })
      })
      .catch(() => {
        if (isMounted) setError('Failed to load cancellation data.')
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [airportIcao])

  if (loading) {
    return (
      <section className="cancellation-section" aria-labelledby="cancel-heading">
        <h2 id="cancel-heading">Cancellations — {airportIcao}</h2>
        <p aria-busy="true">Loading cancellation data…</p>
      </section>
    )
  }
  if (error) {
    return (
      <section className="cancellation-section" aria-labelledby="cancel-heading">
        <h2 id="cancel-heading">Cancellations — {airportIcao}</h2>
        <p role="alert">{error}</p>
      </section>
    )
  }
  if (!data || (data.carriers.length === 0 && data.routes.length === 0)) {
    return (
      <section className="cancellation-section" aria-labelledby="cancel-heading">
        <h2 id="cancel-heading">Cancellations — {airportIcao}</h2>
        <p>No cancellation data available. Run the BTS pipeline first.</p>
      </section>
    )
  }

  const sample = data.carriers[0] ?? data.routes[0]
  const periodCaption = sample
    ? `BTS data: ${fmtDate(sample.period_start)} – ${fmtDate(sample.period_end)}`
    : null

  return (
    <section className="cancellation-section" aria-labelledby="cancel-heading">
      <h2 id="cancel-heading">Cancellations — {airportIcao}</h2>
      {periodCaption && <p className="period-caption">{periodCaption}</p>}
      <div className="cancellation-grid">
        <div className="chart-wrap">
          <CarrierBar airportIcao={airportIcao} carriers={data.carriers} />
        </div>
        <div className="chart-wrap">
          <RouteBar airportIcao={airportIcao} routes={data.routes} />
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 4: Create the section CSS**

`frontend/src/components/CancellationSection/CancellationSection.css`:

```css
.cancellation-section {
  margin-block-start: var(--space-2xl);
  padding-block-start: var(--space-2xl);
  border-block-start: var(--rule);
}

.cancellation-section h2 {
  margin-block-end: var(--space-md);
  display: flex;
  align-items: baseline;
  gap: var(--space-sm);
}

.cancellation-section h2::before {
  content: '03';
  font-family: var(--font-mono);
  font-size: var(--text-eyebrow);
  color: var(--color-ink-subtle);
  letter-spacing: 0.1em;
  font-weight: 500;
}

.period-caption {
  font-family: var(--font-mono);
  font-size: var(--text-eyebrow);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--color-ink-subtle);
  margin-block-end: var(--space-lg);
}

.cancellation-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-xl);
}

@media (min-width: 900px) {
  .cancellation-grid {
    grid-template-columns: 1fr 1fr;
  }
}

.chart-wrap {
  background: var(--color-bg-raised);
  border: var(--rule);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
  box-shadow: var(--shadow-soft);
}
```

- [ ] **Step 5: Render section in `App.tsx`**

Open `frontend/src/App.tsx`. Replace contents with:

```tsx
import { Component, ReactNode } from 'react'
import FlightLookup from './components/FlightLookup/FlightLookup'
import TimelinessDashboard from './components/TimelinessDashboard/TimelinessDashboard'
import CancellationSection from './components/CancellationSection/CancellationSection'

interface ErrorBoundaryState {
  error: Error | null
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <main>
          <h1>TravelPal</h1>
          <p role="alert" style={{ color: 'red' }}>
            Failed to load: {this.state.error.message}
          </p>
        </main>
      )
    }
    return this.props.children
  }
}

const AIRPORT_ICAO = import.meta.env.VITE_AIRPORT_ICAO ?? 'KJFK'

export default function App() {
  return (
    <ErrorBoundary>
      <main>
        <header>
          <h1>TravelPal</h1>
          <p>Flight performance analytics for {AIRPORT_ICAO}</p>
        </header>
        <TimelinessDashboard airportIcao={AIRPORT_ICAO} />
        <FlightLookup airportIcao={AIRPORT_ICAO} />
        <CancellationSection airportIcao={AIRPORT_ICAO} />
      </main>
    </ErrorBoundary>
  )
}
```

- [ ] **Step 6: Run vitest**

```bash
cd frontend
npx vitest run --reporter=basic
```

Expected: all tests pass; CancellationSection adds 6 tests → total 22 passes.

- [ ] **Step 7: Run tsc + build**

```bash
npx tsc --noEmit
npm run build
```

Expected: both exit 0.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/CancellationSection \
        frontend/src/App.tsx
git commit -m "feat(frontend): add CancellationSection with carrier + route Highcharts bars"
```

---

## Task 18: Update Playwright smoke E2E

**Files:**
- Modify: `frontend/tests/e2e/smoke.spec.ts`

- [ ] **Step 1: Read current file**

```bash
cat frontend/tests/e2e/smoke.spec.ts
```

Note its current shape — likely a single `expect(page.locator('h1')).toBeVisible()` test.

- [ ] **Step 2: Replace with a fuller smoke**

```typescript
import { test, expect } from '@playwright/test'

test('landing page loads with all three sections', async ({ page }) => {
  await page.goto('/')

  await expect(page.locator('h1', { hasText: 'TravelPal' })).toBeVisible()
  await expect(
    page.getByRole('heading', { level: 2, name: /historic timeliness/i })
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { level: 2, name: /flight lookup/i })
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { level: 2, name: /cancellations/i })
  ).toBeVisible({ timeout: 15000 })

  // Highcharts renders an SVG per chart (Carriers + Routes).
  await expect(page.locator('.cancellation-section svg')).toHaveCount(2, {
    timeout: 15000,
  })
})

test('no console errors on first load', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', m => {
    if (m.type() === 'error') errors.push(m.text())
  })
  await page.goto('/', { waitUntil: 'networkidle' })
  await page.waitForTimeout(3000)
  expect(errors, errors.join('\n')).toEqual([])
})
```

- [ ] **Step 3: Run Playwright locally if dev server is up**

```bash
cd frontend
# In a separate terminal, ensure `npm run dev` is running on :5173
npx playwright test --reporter=line
```

Expected: 2 PASS. (Skip this step in CI; the existing E2E job runs Playwright with the stub-mode pipeline.)

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/e2e/smoke.spec.ts
git commit -m "test(e2e): assert cancellation section + Highcharts SVGs present"
```

---

## Task 19: Add gated live BTS download integration test

**Files:**
- Create: `pipeline/tests/integration/test_integration_bts_download.py`

- [ ] **Step 1: Write the test**

```python
"""Live BTS download — gated behind TRAVELPAL_BTS_LIVE=1.

CI never runs this. Local devs validate against the real BTS endpoint by:

    TRAVELPAL_BTS_LIVE=1 uv run pytest \\
        tests/integration/test_integration_bts_download.py -v

Mirrors the live OpenSky-token gate pattern in test_integration_opensky_auth.py.
"""

import asyncio
import io
import os
import zipfile

import pytest

from pipeline.resources.bts import BTSResource


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("TRAVELPAL_BTS_LIVE") != "1",
    reason="set TRAVELPAL_BTS_LIVE=1 to hit transtats.bts.gov for real",
)
def test_live_bts_download_returns_valid_zip_with_many_rows():
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=None,
    )
    payload = asyncio.run(resource.download_month(2024, 1))

    assert payload[:2] == b"PK", "Payload must be a ZIP"
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        assert csv_names, "ZIP must contain at least one CSV"
        sample = zf.read(csv_names[0])
        # Crude row-count proxy: 100k+ flights/month nationally.
        assert sample.count(b"\n") > 100_000, (
            f"Expected ≥100k rows in BTS January 2024; got {sample.count(b'\\n')}"
        )
```

- [ ] **Step 2: Confirm test is skipped without env var**

```bash
cd pipeline
uv run pytest tests/integration/test_integration_bts_download.py -v
```

Expected: 1 SKIPPED.

- [ ] **Step 3: Commit**

```bash
git add pipeline/tests/integration/test_integration_bts_download.py
git commit -m "test(R19): gated live-BTS-download integration test"
```

---

## Task 20: Add Iceberg round-trip integration test

**Files:**
- Create: `pipeline/tests/integration/test_integration_iceberg_bts.py`

- [ ] **Step 1: Look at the existing iceberg integration helper**

```bash
cat pipeline/tests/integration/_iceberg.py
```

Note any shared fixtures (catalog setup, namespace cleanup).

- [ ] **Step 2: Write the test**

```python
"""End-to-end BTS → Iceberg round-trip against real Nessie + SeaweedFS.

Uses the BTS fixture so no network call to transtats.bts.gov is made.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pyarrow as pa
import pytest

from pipeline.assets.bts_on_time import bts_on_time
from pipeline.config import PipelineConfig
from pipeline.resources.bts import BTSResource
from pipeline.resources.nessie import NessieResource

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bts_kjfk_2024_01.csv.zip"


@pytest.mark.integration
def test_bts_on_time_round_trip(nessie_resource: NessieResource, raw_bucket: str):
    config = PipelineConfig.model_validate(
        {
            "airport_icao": "KJFK",
            "ingest_start_date": "2024-01-01",
            "ingest_end_date": "2024-01-08",
            "SEAWEEDFS_S3_ENDPOINT": "http://localhost:8333",
            "seaweedfs_access_key": "admin",
            "seaweedfs_secret_key": "admin",
            "nessie_endpoint": nessie_resource.endpoint,
            "raw_bucket": raw_bucket,
            "bts_fixture_file": str(FIXTURE),
        }
    )
    bts = BTSResource(endpoint="https://transtats.bts.gov/PREZIP", fixture_file=FIXTURE)

    context = MagicMock()
    context.partition_key = "2024-01"

    bts_on_time(
        context=context,
        pipeline_config=config,
        bts=bts,
        nessie=nessie_resource,
    )

    table = nessie_resource.catalog.load_table("flights.bts_on_time")
    arrow_table: pa.Table = table.scan().to_arrow()

    assert arrow_table.num_rows == 9, "9 KJFK rows in fixture"
    schema_names = set(arrow_table.column_names)
    assert {
        "flight_date",
        "carrier_iata",
        "origin_iata",
        "destination_iata",
        "cancelled",
        "diverted",
        "year_month",
    }.issubset(schema_names)
    year_months = set(arrow_table.column("year_month").to_pylist())
    assert year_months == {"2024-01"}
```

The `nessie_resource` and `raw_bucket` fixtures live in
`pipeline/tests/integration/conftest.py`. If they don't, the developer
should crib them from `test_integration_iceberg.py`.

- [ ] **Step 3: Run the integration test (requires Docker stack up)**

```bash
cd /Users/axel/code/travel_pal
just up   # if not already running
cd pipeline
uv run pytest tests/integration/test_integration_iceberg_bts.py -v -m integration
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add pipeline/tests/integration/test_integration_iceberg_bts.py
git commit -m "test(integration): BTS → Iceberg round-trip via real Nessie + SeaweedFS"
```

---

## Task 21: Update memory file for OpenSky cancellation note

**Files:**
- Modify: `docs/superpowers/skills/travelpal-opensky-adapter/SKILL.md`

- [ ] **Step 1: Edit the SKILL note**

Find the line in `docs/superpowers/skills/travelpal-opensky-adapter/SKILL.md`:

```
OpenSky only records flights that have both a departure and an arrival. Cancelled flights never appear. **`cancellation_rate` cannot be computed from OpenSky data.** Deferred to Phase 1.
```

Replace with:

```
OpenSky only records flights that have both a departure and an arrival. Cancelled flights never appear. **`cancellation_rate` cannot be computed from OpenSky data.** Phase 1 sources cancellations from BTS On-Time Performance via `pipeline/pipeline/resources/bts.py` + `pipeline/pipeline/assets/bts_on_time.py`; see `docs/superpowers/specs/2026-06-05-phase1-cancellation-rate-design.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/skills/travelpal-opensky-adapter/SKILL.md
git commit -m "docs(skill): point opensky-adapter at BTS cancellation source"
```

---

## Task 22: Final pre-PR verification + push + open PR

- [ ] **Step 1: Run the full backend unit + dbt test suite**

```bash
cd pipeline
uv run pytest -q -m "not integration"
```

Expected: all PASS, no failures, ≥80% coverage.

- [ ] **Step 2: Run lint + typecheck**

```bash
uvx ruff check .
uvx ruff format --check .
uvx ty check --python "$(uv python find)"
```

Expected: All checks passed.

- [ ] **Step 3: Run frontend tests + build**

```bash
cd ../frontend
npx vitest run --reporter=basic
npx tsc --noEmit
npm run build
```

Expected: 22+ tests pass, no tsc errors, build exits 0.

- [ ] **Step 4: Push the branch**

```bash
cd ..
git push -u origin feat/phase1-cancellation-rate
```

- [ ] **Step 5: Open the PR**

```bash
gh pr create \
  --title "feat: Phase 1 cancellation rate end-to-end (BTS + Highcharts)" \
  --body "$(cat <<'EOF'
## Summary
End-to-end cancellation-rate feature for KJFK, sourced from US BTS On-Time
Performance:

- **Pipeline:** new `BTSResource` (pyreqwest, fixture-mode bypass) + monthly-
  partitioned `bts_on_time` Dagster asset writing to Iceberg `flights.bts_on_time`.
  `transformed_flights` now depends on `bts_on_time` and runs `dbt seed && dbt run`.
- **dbt:** new seeds `dim_airport` (OurAirports ~80k) + `dim_carrier`
  (OpenFlights airlines.dat ~6k); new staging `stg_bts_on_time` (IATA → ICAO);
  new marts `agg_carrier_cancellations` + `agg_route_cancellations`.
- **Exports:** `frontend_exports` filters both new marts to `airport_icao` and
  uploads `carrier_cancellations.parquet` + `route_cancellations.parquet`.
- **Frontend:** new `<CancellationSection>` with two Highcharts horizontal bars
  (top-10 carriers, top-10 routes by cancellation rate). Period caption from
  `period_start` / `period_end`.
- **Licensing:** Highcharts is used under the free non-commercial license; see
  `LICENSING.md`.

## Test plan
- [x] `uv run pytest -q -m 'not integration'` — all unit tests pass
- [x] `uvx ruff check .` + `format --check` + `ty check` — clean
- [x] `npx vitest run` — frontend unit tests pass
- [x] `npx tsc --noEmit` — clean
- [ ] `just up && uv run pytest -q -m integration` — integration suite
- [ ] CI green (ruff, ty, pytest, eslint, tsc, vitest, playwright smoke)
- [ ] Manual UAT: `just nuke && just up && just materialize` — confirm both
      cancellation parquets land in `frontend-exports/KJFK/` and dashboard
      renders both bar charts

## Out of scope (tracked)
- F1.3 Competitor Comparison Matrix (will reuse `dim_carrier`)
- F1.4 Temporal Bottleneck Heatmap
- sqlglot ANSI → DuckDB transpilation layer
EOF
)"
```

Expected: PR opened. Output URL printed.

- [ ] **Step 6: Watch CI**

```bash
gh pr checks --watch
```

Expected: all checks green.

---

## Self-Review

**Spec coverage:**

| Spec section | Plan task |
|--------------|-----------|
| §2 Architecture overview | T1 (license), T2 (Highcharts), T8 (BTSResource), T9 (asset), T10 (wiring), T11 (chained dbt) |
| §3 File structure — pipeline | T6 (config), T8, T9, T10, T11, T14 (frontend_exports) |
| §3 File structure — tests | T7 (BTS fixture), T15 (parquet stubs), T8/T9/T10/T11/T14 (test files), T19/T20 (integration) |
| §3 File structure — frontend | T2 (deps), T16 (queries), T17 (components), T18 (e2e) |
| §3 File structure — docs | T1 (LICENSING), T21 (memory file) |
| §4 Data contracts — Iceberg schema | T9 |
| §4 Data contracts — dbt seeds | T3, T4, T5 |
| §4 Data contracts — `stg_bts_on_time` | T12 |
| §4 Data contracts — marts | T13 |
| §4 Data contracts — frontend types | T16 |
| §4 Data contracts — S3 keys | T14 |
| §5 Testing — unit | T8, T9, T11, T14 |
| §5 Testing — dbt file content | T5, T12, T13 |
| §5 Testing — integration | T20 (Iceberg), T19 (live), T22 (full integration suite via `just up`) |
| §5 Testing — frontend | T17 |
| §5 Testing — E2E | T18 |
| §6 R1 BTS download stability | T8 (retry), T19 (gated live) — note: SeaweedFS ZIP cache deferred (low-risk in fixture-driven CI) |
| §6 R2 Mapping coverage | T12 (INNER JOIN + NULLIF guards) — non-blocking dbt test deferred |
| §6 R3 OpenFlights staleness | accepted, no override layer |
| §6 R4 Highcharts license | T1 |
| §6 R5 Mart predicate | T14 |
| §6 R6 PyIceberg `update_schema` | NOT covered — see fix below |
| §6 R7 Period caption | T17 (CancellationSection.tsx) |
| §6 R8 Seed compile time | accepted |

**Gaps found + fixed inline:**

- **R1 SeaweedFS ZIP cache:** spec said "Yes — small LOC, big resilience win" (Q1). Plan defers it. Adding **Task 23** below.
- **R2 non-blocking dbt coverage test:** spec called for `count(stg_bts) / count(raw_bts) > 0.99`. Adding to **Task 12** as an addendum step (custom dbt singular test).
- **R6 `update_schema`:** the asset currently calls `create_table` only when missing. To honour R6, the asset should also call `update_schema()` idempotently before append in case the schema drifts. Adding to **Task 9** as a follow-up step below.

**Placeholder scan:** all "Run X / Expected Y" lines complete. No `TBD`/`TODO` strings.

**Type consistency:**
- `BTSResource(endpoint, fixture_file)` consistent across T8, T10, T19, T20.
- `bts_on_time(context, pipeline_config, bts, nessie)` signature consistent across T9, T10, T20.
- `CarrierCancellation` / `RouteCancellation` shapes match between T16 (query types) and T14 (test fixtures).
- `_MART_AIRPORT_PREDICATE` keys match `_MARTS` tuple in T14.
- Highcharts `options.title.text` is `Carriers — KJFK` / `Routes — KJFK`; test mock matches via `hc-${title}` data-testid in T17.

---

## Task 9 addendum (R6): idempotent `update_schema`

After Step 3 in Task 9, before `iceberg_table.append(table)`, insert:

```python
    # R6: schema-drift safety. update_schema() is a no-op when the table
    # schema already matches the local _SCHEMA, so this is cheap and prevents
    # silent column drops if the local schema gains a field later.
    iceberg_table = catalog.load_table(_TABLE_IDENTIFIER)
    with iceberg_table.update_schema() as upd:
        upd.union_by_name(_SCHEMA)
```

(Place immediately before the `iceberg_table.append(table)` line; remove any
duplicate `iceberg_table = catalog.load_table(...)` that results.)

Final asset bottom looks like:

```python
    catalog = nessie.catalog
    catalog.create_namespace_if_not_exists("flights")
    if not catalog.table_exists(_TABLE_IDENTIFIER):
        catalog.create_table(_TABLE_IDENTIFIER, schema=_SCHEMA)

    iceberg_table = catalog.load_table(_TABLE_IDENTIFIER)
    with iceberg_table.update_schema() as upd:
        upd.union_by_name(_SCHEMA)
    iceberg_table.append(table)
```

Add a unit test in Task 9 Step 1, alongside the others:

```python
@pytest.mark.unit
def test_bts_on_time_calls_update_schema_before_append(tmp_path):
    """R6: union_by_name on update_schema must run before append so a
    schema-drift event can't drop columns silently.
    """
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    nessie = MagicMock()
    nessie.catalog.table_exists.return_value = True
    update_ctx = MagicMock()
    nessie.catalog.load_table.return_value.update_schema.return_value.__enter__ = (
        lambda self: update_ctx
    )
    nessie.catalog.load_table.return_value.update_schema.return_value.__exit__ = (
        lambda *args: None
    )

    context = MagicMock()
    context.partition_key = "2024-01"

    bts_on_time(
        context=context,
        pipeline_config=config,
        bts=bts_resource,
        nessie=nessie,
    )

    update_ctx.union_by_name.assert_called_once()
    nessie.catalog.load_table.return_value.append.assert_called_once()
```

---

## Task 12 addendum (R2): coverage test

After Step 5, add:

- [ ] **Step 6: Add a non-blocking coverage test**

Create `pipeline/transforms/tests/stg_bts_coverage.sql`:

```sql
-- Non-blocking signal that >1% of BTS rows are dropping out of stg_bts_on_time
-- because of a missing IATA→ICAO mapping. dbt singular test: returns rows for
-- failures. Severity warn so it does not block dbt build.
{{ config(severity='warn') }}

WITH raw AS (
    SELECT COUNT(*) AS n FROM nessie.flights.bts_on_time
),
stg AS (
    SELECT COUNT(*) AS n FROM {{ ref('stg_bts_on_time') }}
)
SELECT raw.n AS raw_rows, stg.n AS stg_rows
FROM raw, stg
WHERE stg.n * 1.0 / NULLIF(raw.n, 0) < 0.99
```

- [ ] **Step 7: Test the test exists**

Append to `pipeline/tests/test_dbt_models.py`:

```python
@pytest.mark.unit
def test_stg_bts_coverage_test_exists() -> None:
    """A dbt singular test guarding the IATA→ICAO mapping coverage must exist."""
    sql = (TRANSFORMS_DIR / "tests" / "stg_bts_coverage.sql").read_text()
    assert "stg_bts_on_time" in sql
    assert "0.99" in sql
    assert "severity='warn'" in sql
```

- [ ] **Step 8: Run + commit**

```bash
cd pipeline
uv run pytest tests/test_dbt_models.py::test_stg_bts_coverage_test_exists -v
git add pipeline/transforms/tests/stg_bts_coverage.sql pipeline/tests/test_dbt_models.py
git commit -m "test(dbt): warn-level coverage test for stg_bts_on_time mapping"
```

---

## Task 23: Cache BTS ZIPs in SeaweedFS (R1)

**Files:**
- Modify: `pipeline/pipeline/assets/bts_on_time.py`
- Modify: `pipeline/tests/test_asset_bts_on_time.py`

- [ ] **Step 1: Write the failing test**

Append to `pipeline/tests/test_asset_bts_on_time.py`:

```python
@pytest.mark.unit
def test_bts_on_time_uses_seaweedfs_cache_when_present(tmp_path):
    """When SeaweedFS already holds a cached BTS ZIP for this partition,
    the asset must read from the cache and NOT call BTSResource.download_month.
    """
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    seaweedfs = MagicMock()
    seaweedfs.get_object.return_value = FIXTURE_PATH.read_bytes()

    nessie = MagicMock()
    nessie.catalog.table_exists.return_value = True
    nessie.catalog.load_table.return_value.update_schema.return_value.__enter__ = (
        lambda self: MagicMock()
    )
    nessie.catalog.load_table.return_value.update_schema.return_value.__exit__ = (
        lambda *args: None
    )

    context = MagicMock()
    context.partition_key = "2024-01"

    bts_on_time(
        context=context,
        pipeline_config=config,
        bts=bts_resource,
        nessie=nessie,
        seaweedfs=seaweedfs,
    )

    bts_resource.download_month.assert_not_called()
    seaweedfs.get_object.assert_called_once_with(
        bucket="bts-raw", key="2024-01.zip"
    )


@pytest.mark.unit
def test_bts_on_time_writes_to_cache_after_download(tmp_path):
    """When SeaweedFS does not have a cached ZIP, asset downloads from BTS,
    writes the bytes to seaweedfs.put_object, then proceeds with append.
    """
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    seaweedfs = MagicMock()
    seaweedfs.get_object.side_effect = FileNotFoundError("no cache")

    nessie = MagicMock()
    nessie.catalog.table_exists.return_value = True
    nessie.catalog.load_table.return_value.update_schema.return_value.__enter__ = (
        lambda self: MagicMock()
    )
    nessie.catalog.load_table.return_value.update_schema.return_value.__exit__ = (
        lambda *args: None
    )

    context = MagicMock()
    context.partition_key = "2024-01"

    bts_on_time(
        context=context,
        pipeline_config=config,
        bts=bts_resource,
        nessie=nessie,
        seaweedfs=seaweedfs,
    )

    bts_resource.download_month.assert_called_once_with(2024, 1)
    seaweedfs.put_object.assert_called_once()
    args = seaweedfs.put_object.call_args.kwargs
    assert args["bucket"] == "bts-raw"
    assert args["key"] == "2024-01.zip"
    assert args["body"][:2] == b"PK"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd pipeline
uv run pytest tests/test_asset_bts_on_time.py::test_bts_on_time_uses_seaweedfs_cache_when_present \
              tests/test_asset_bts_on_time.py::test_bts_on_time_writes_to_cache_after_download -v
```

Expected: FAIL — `seaweedfs` not a parameter; `get_object` / `put_object` not on `SeaweedFSResource`.

- [ ] **Step 3: Add `get_object` + `put_object` to `SeaweedFSResource`**

Open `pipeline/pipeline/resources/seaweedfs.py`. After `upload_parquet`, add:

```python
    def get_object(self, *, bucket: str, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=bucket, Key=key)
        except self._client.exceptions.NoSuchKey as exc:
            raise FileNotFoundError(f"s3://{bucket}/{key} not found") from exc
        return response["Body"].read()  # type: ignore[no-any-return]

    def put_object(self, *, bucket: str, key: str, body: bytes) -> None:
        self._client.put_object(Bucket=bucket, Key=key, Body=body)
```

- [ ] **Step 4: Update `bts_on_time` asset**

In `pipeline/pipeline/assets/bts_on_time.py`, change the asset signature and download path:

```python
from pipeline.resources.seaweedfs import SeaweedFSResource

# ... (top-of-file imports unchanged otherwise)

@asset(partitions_def=BTS_PARTITIONS)
def bts_on_time(
    context: AssetExecutionContext,
    pipeline_config: ResourceParam[PipelineConfig],
    bts: ResourceParam[BTSResource],
    nessie: ResourceParam[NessieResource],
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None:
    year_str, month_str = context.partition_key.split("-")
    year = int(year_str)
    month = int(month_str)

    cache_key = f"{context.partition_key}.zip"
    try:
        zip_bytes = seaweedfs.get_object(
            bucket=pipeline_config.bts_cache_bucket,
            key=cache_key,
        )
        context.log.info(
            f"BTS partition {context.partition_key} loaded from cache "
            f"s3://{pipeline_config.bts_cache_bucket}/{cache_key}"
        )
    except FileNotFoundError:
        zip_bytes = asyncio.run(bts.download_month(year, month))
        seaweedfs.put_object(
            bucket=pipeline_config.bts_cache_bucket,
            key=cache_key,
            body=zip_bytes,
        )
        context.log.info(
            f"BTS partition {context.partition_key} downloaded and cached "
            f"to s3://{pipeline_config.bts_cache_bucket}/{cache_key}"
        )

    table = extract_csv_from_zip(
        zip_bytes,
        origin_iata=_airport_iata(pipeline_config.airport_icao),
    )
    # … rest unchanged
```

- [ ] **Step 5: Update existing tests in Task 9**

The Task 9 unit tests (`test_bts_on_time_creates_table_and_appends_for_partition`,
`test_bts_on_time_no_op_on_zero_rows`, etc.) must now pass a `seaweedfs` mock
where `get_object` raises `FileNotFoundError`. Add this `seaweedfs` arg:

```python
seaweedfs = MagicMock()
seaweedfs.get_object.side_effect = FileNotFoundError("no cache")
# … invoke asset with seaweedfs=seaweedfs
```

Apply to all 3 existing Task 9 tests.

- [ ] **Step 6: Run all asset tests**

```bash
uv run pytest tests/test_asset_bts_on_time.py -v
```

Expected: all 5 PASS.

- [ ] **Step 7: Update Definitions wiring**

Confirm `seaweedfs` is already in `_make_resources()` from Task 10 — it is.
The asset will pick it up automatically because `ResourceParam[SeaweedFSResource]`
matches the `"seaweedfs"` resource key.

- [ ] **Step 8: Commit**

```bash
git add pipeline/pipeline/resources/seaweedfs.py \
        pipeline/pipeline/assets/bts_on_time.py \
        pipeline/tests/test_asset_bts_on_time.py
git commit -m "feat(bts): cache downloaded ZIPs in SeaweedFS (R1 resilience)"
```

---

## Final Task 24: Re-run Task 22 and re-push

After Tasks 9 / 12 / 23 addenda, redo Task 22 Steps 1–6 to ensure everything is
green, then push the additional commits.

```bash
cd pipeline
uv run pytest -q -m "not integration"
uvx ruff check . && uvx ruff format --check . && uvx ty check --python "$(uv python find)"
cd ../frontend && npx vitest run --reporter=basic && npx tsc --noEmit && npm run build
cd ..
git push
gh pr checks --watch
```
