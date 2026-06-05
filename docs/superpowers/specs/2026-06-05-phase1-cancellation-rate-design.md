# TravelPal — Phase 1 Cancellation Rate Design Spec

**Date:** 2026-06-05
**Scope:** End-to-end cancellation-rate feature for KJFK — new BTS data source, dbt seeds for airport + carrier dimensions, two new aggregation marts, and a dashboard section with carrier and route bar charts.
**Status:** Approved (sections 1–5 walked through and approved by user 2026-06-05).

---

## 1. Goals & Non-Goals

### Goals

- Surface a `cancellation_rate` metric per airport, per carrier, and per route on the public dashboard.
- Establish a reusable BTS On-Time Performance ingestion pipeline that future phases can extend (delays-by-carrier, weather-cancellation breakdown, multi-airport rollouts).
- Stand up canonical airport (`dim_airport`) and carrier (`dim_carrier`) reference dimensions, ICAO-keyed.
- Add a cancellation section to the dashboard with two carrier and route Highcharts bar charts.

### Non-Goals

- F1.3 Competitor Comparison Matrix — explicitly out (uses the new carrier dim but ships in a separate spec).
- F1.4 Temporal Bottleneck Heatmap — explicitly out.
- sqlglot ANSI → DuckDB transpilation layer — explicitly out (architecturally on the Phase 1 enabler list but defers cleanly).
- Real-time / sub-day cancellation data — BTS is monthly batch with ~3-month lag.
- Non-US airports — BTS is US-only. KJFK only for v1.

---

## 2. Architecture Overview

### Data flow

```
BTS transtats.bts.gov (monthly ZIP)
  └─ pyreqwest.AsyncClient.POST → ZIP bytes
       └─ stdlib zipfile + pyarrow.csv.read_csv (project required columns)
            └─ PyIceberg append → Iceberg flights.bts_on_time (partitioned by year_month)

dbt seeds (committed CSV)
  ├─ dim_airport  (icao_pk, iata, name, city, country, lat, lon, airport_type)  — OurAirports full ~80k
  └─ dim_carrier  (icao_pk, iata, name, callsign, country, active)              — OpenFlights airlines.dat ~6k

dbt models
  ├─ stg_bts_on_time      (clean BTS columns, IATA → ICAO via dim_airport, dim_carrier)
  ├─ marts/agg_carrier_cancellations  (origin_icao, carrier_icao → total_scheduled, cancelled, cancellation_rate)
  └─ marts/agg_route_cancellations    (origin_icao, destination_icao → ...)

Dagster
  ├─ bts_on_time          (MonthlyPartitionsDefinition, manual backfill)
  ├─ transformed_flights  (existing — gains AssetIn dependency on bts_on_time)
  └─ frontend_exports     (existing — gains carrier_cancellations.parquet, route_cancellations.parquet)

Frontend
  └─ <CancellationSection> below <FlightLookup>
       ├─ Highcharts horizontal bar: top-10 carriers by cancellation rate
       └─ Highcharts horizontal bar: top-10 routes by cancellation rate
       (queries via DuckDB-WASM read_parquet, same pattern as TimelinessDashboard)
```

### Key boundaries

- BTS ingestion is an independent Dagster asset, not coupled to OpenSky's daily run cadence.
- Cancellation marts are BTS-only — they do not modify the existing OpenSky-derived `agg_daily_timeliness` and `agg_route_timeliness` marts. Source-of-truth purity.
- `dim_airport` and `dim_carrier` are dbt seeds (committed CSV), not Dagster assets — slowly-changing reference data.
- ICAO is canonical PK across the warehouse; IATA carried as an attribute on the dim and as raw columns in the Iceberg landing table.

### Tech stack

- pyreqwest (existing) for BTS HTTP, mirroring `OpenSkyResource` pattern.
- PyArrow + PyIceberg (existing) for raw Iceberg landing.
- dbt-duckdb (existing) for staging and marts.
- Dagster (existing) for orchestration; `MonthlyPartitionsDefinition` for `bts_on_time`.
- Highcharts + `highcharts-react-official` (new frontend deps) under the free non-commercial license.

---

## 3. File Structure & Responsibilities

### Pipeline (`pipeline/`)

| File | Status | Responsibility |
|------|--------|----------------|
| `pipeline/resources/bts.py` | new | `BTSResource(ConfigurableResource)` — pyreqwest client, `download_month(year, month) → bytes`, retry/backoff, `bts_fixture_file` env override for fixture mode |
| `pipeline/assets/bts_on_time.py` | new | `bts_on_time` asset, `MonthlyPartitionsDefinition` (start `2024-01`), parses ZIP via stdlib zipfile, projects required columns, appends to Iceberg `flights.bts_on_time` |
| `pipeline/assets/__init__.py` | modify | export new asset |
| `pipeline/__init__.py` | modify | wire `BTSResource` into `Definitions`, add `bts_on_time` to assets, attach `MonthlyPartitionsDefinition` |
| `pipeline/config.py` | modify | add `bts_endpoint`, `bts_fixture_file: Path \| None` to `PipelineConfig` |
| `pipeline/assets/transformed_flights.py` | modify | add `AssetIn("bts_on_time", dagster_type=Nothing)` so dbt build waits on BTS landing |
| `pipeline/assets/frontend_exports.py` | modify | add `agg_carrier_cancellations` and `agg_route_cancellations` to `_MARTS`, `_EXPORT_KEYS`, `_MART_AIRPORT_PREDICATE` |
| `pipeline/transforms/seeds/dim_airport.csv` | new | OurAirports full export, ICAO PK |
| `pipeline/transforms/seeds/dim_carrier.csv` | new | OpenFlights airlines.dat, ICAO PK |
| `pipeline/transforms/dbt_project.yml` | modify | add `seeds:` block (`+quote_columns: false`, materialised location) |
| `pipeline/transforms/models/staging/stg_bts_on_time.sql` | new | clean BTS columns, IATA → ICAO via `dim_airport`, IATA → ICAO via `dim_carrier`, type casts |
| `pipeline/transforms/models/staging/schema.yml` | modify | add `not_null` tests on `origin_icao`, `carrier_icao`, `flight_date`, `cancelled` |
| `pipeline/transforms/models/marts/agg_carrier_cancellations.sql` | new | grouped by `(origin_icao, carrier_icao)`: total_scheduled, cancelled, cancellation_rate, period_start, period_end |
| `pipeline/transforms/models/marts/agg_route_cancellations.sql` | new | grouped by `(origin_icao, destination_icao)`: same metrics |

### Tests (`pipeline/tests/`)

| File | Status | Responsibility |
|------|--------|----------------|
| `tests/fixtures/bts_kjfk_2024_01.csv.zip` | new | tiny BTS fixture, 50 KJFK rows, 2 carriers, ~5 cancelled |
| `tests/fixtures/carrier_cancellations.parquet` | new | stub Parquet for E2E (when `TRAVELPAL_BTS_FIXTURE_FILE` set) |
| `tests/fixtures/route_cancellations.parquet` | new | same |
| `tests/test_bts.py` | new | unit: BTSResource parses fixture, retries, missing-month |
| `tests/test_asset_bts_on_time.py` | new | unit: asset filters, appends to Iceberg, partition resolution, no-op on zero rows |
| `tests/test_dbt_models.py` | modify | parametrized assertions for new marts and seeds |
| `tests/integration/test_integration_dbt_build.py` | modify | dbt seed step, new marts produced, joins resolve |
| `tests/integration/test_integration_iceberg_bts.py` | new | round-trip BTS → Iceberg via real Nessie+SeaweedFS fixture |
| `tests/integration/test_integration_bts_download.py` | new (gated) | live BTS download, gated behind `TRAVELPAL_BTS_LIVE=1` |

### Frontend (`frontend/`)

| File | Status | Responsibility |
|------|--------|----------------|
| `frontend/package.json` | modify | add `highcharts`, `highcharts-react-official` deps |
| `frontend/src/db/queries.ts` | modify | add `queryCarrierCancellations(airport)`, `queryRouteCancellations(airport)`, types |
| `frontend/src/components/CancellationSection/CancellationSection.tsx` | new | section component, fetches both queries in parallel, renders 2 Highcharts bars |
| `frontend/src/components/CancellationSection/CarrierBar.tsx` | new | Highcharts horizontal bar wrapper, props = data + airport |
| `frontend/src/components/CancellationSection/RouteBar.tsx` | new | Highcharts horizontal bar wrapper, props = data + airport |
| `frontend/src/components/CancellationSection/CancellationSection.css` | new | section styling, consumes design tokens |
| `frontend/src/components/CancellationSection/CancellationSection.test.tsx` | new | vitest: loading / empty / error / populated states |
| `frontend/src/App.tsx` | modify | render `<CancellationSection />` after `<FlightLookup />` |
| `frontend/tests/e2e/smoke.spec.ts` | modify | assert cancellation section heading + bars rendered |

### Documentation

| File | Status | Responsibility |
|------|--------|----------------|
| `docs/superpowers/skills/travelpal-opensky-adapter/SKILL.md` | modify | append BTS-as-truth-source note next to existing "cancellation_rate cannot be computed from OpenSky" line |
| `LICENSING.md` | new | Highcharts non-commercial use note (R4) |

---

## 4. Data Contracts

### BTS On-Time Performance — projected columns

| Source col | Type | Notes |
|------------|------|-------|
| `FlightDate` | string `YYYY-MM-DD` | parse to `pa.date32()` |
| `Reporting_Airline` | string IATA | join → `dim_carrier.iata → carrier_icao` |
| `Tail_Number` | string | nullable |
| `Flight_Number_Reporting_Airline` | string | flight number |
| `Origin` | string IATA | join → `dim_airport.iata → origin_icao` |
| `Dest` | string IATA | join → `dim_airport.iata → destination_icao` |
| `CRSDepTime` | string `HHMM` | scheduled departure local time |
| `Cancelled` | string/float `0.00`/`1.00` | cast to bool |
| `CancellationCode` | string `A`/`B`/`C`/`D`/empty | A=carrier, B=weather, C=NAS, D=security |
| `Diverted` | string/float | cast to bool |

### Iceberg `flights.bts_on_time`

```python
schema = sch.Schema(
    NestedField(1,  "flight_date",       DateType(),    required=True),
    NestedField(2,  "carrier_iata",      StringType(),  required=True),
    NestedField(3,  "flight_number",     StringType(),  required=False),
    NestedField(4,  "tail_number",       StringType(),  required=False),
    NestedField(5,  "origin_iata",       StringType(),  required=True),
    NestedField(6,  "destination_iata",  StringType(),  required=True),
    NestedField(7,  "crs_dep_time",      StringType(),  required=False),
    NestedField(8,  "cancelled",         BooleanType(), required=True),
    NestedField(9,  "cancellation_code", StringType(),  required=False),
    NestedField(10, "diverted",          BooleanType(), required=True),
    NestedField(11, "year_month",        StringType(),  required=True),  # "YYYY-MM" partition col
)
```

Carrier and airport stored as IATA at the raw layer (no joins yet); translation happens in `stg_bts_on_time`.

### dbt seeds

`dim_airport.csv` (OurAirports projected schema):

```
icao,iata,name,city,country,lat,lon,airport_type
KJFK,JFK,"John F Kennedy Intl",New York,US,40.6413,-73.7781,large_airport
KLAX,LAX,"Los Angeles Intl",Los Angeles,US,33.9425,-118.4081,large_airport
…
```

- PK `icao`, NOT NULL.
- `iata` may be empty (some airports lack IATA) — filtered out before BTS join.
- ~80k rows, ~3MB committed.

`dim_carrier.csv` (OpenFlights airlines.dat schema):

```
icao,iata,name,callsign,country,active
AAL,AA,"American Airlines",AMERICAN,United States,Y
DAL,DL,"Delta Air Lines",DELTA,United States,Y
…
```

- PK `icao`, NOT NULL.
- ~6k rows, ~400KB committed.
- Note: OpenFlights stopped updating in 2017 — adequate for top-tier US carriers, may miss recent regional/cargo entrants. Override layer deferred (see §6 R3).

### `stg_bts_on_time` (DuckDB dialect)

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

`carrier_name` carried through staging so marts don't re-join `dim_carrier`.

Inner join intentional — rows with unmappable codes drop. Test asserts <1% drop on a known-good month.

### Mart `agg_carrier_cancellations`

```sql
{{ config(location="s3://" ~ env_var('RAW_BUCKET','raw-flights') ~ "/warehouse/marts/" ~ this.name ~ ".parquet") }}
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

### Mart `agg_route_cancellations`

```sql
{{ config(location="s3://" ~ env_var('RAW_BUCKET','raw-flights') ~ "/warehouse/marts/" ~ this.name ~ ".parquet") }}
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

`cancellation_rate` is non-null because `NULLIF(COUNT(*), 0)` only nulls on empty groups, which can't happen post-`GROUP BY`.

### Frontend types (`queries.ts`)

```ts
export interface CarrierCancellation {
  origin_icao: string
  carrier_icao: string
  carrier_name: string
  total_scheduled: number
  cancelled: number
  cancellation_rate: number  // non-null per mart
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
```

### Public S3 keys

- `frontend-exports/{airport}/carrier_cancellations.parquet`
- `frontend-exports/{airport}/route_cancellations.parquet`

Filtered server-side via `frontend_exports._MART_AIRPORT_PREDICATE` (same pattern as Phase 0 marts).

---

## 5. Testing Strategy

### Unit (`tests/test_bts.py`, `tests/test_asset_bts_on_time.py`)

| Test | Asserts |
|------|---------|
| `test_bts_resource_parses_fixture_zip` | `BTSResource(bts_fixture_file=path).download_month(2024, 1)` returns expected ZIP bytes; no network call |
| `test_bts_resource_uses_pyreqwest_post_when_no_fixture` | mock client, asserts POST URL `transtats.bts.gov/PREZIP/...` and form payload |
| `test_bts_resource_retries_on_5xx` | mock 503 → 200; one retry; respects backoff |
| `test_bts_resource_raises_on_missing_month` | 404 / empty ZIP → typed `BTSDownloadError` |
| `test_extract_csv_from_zip_filters_to_airport` | given fixture + `airport_icao=KJFK`, returns `pa.Table` with only origin_iata=JFK or destination_iata=JFK rows |
| `test_extract_handles_iata_without_icao_mapping` | rows with origin_iata=XYZ kept at raw layer; staging-layer test handles drop |
| `test_extract_casts_cancelled_diverted_to_bool` | `"0.00"`/`"1.00"` → false/true |
| `test_asset_bts_on_time_appends_to_iceberg` | mocked Nessie + BTS, asset run for `2024-01` calls `catalog.create_table` (when missing) then `table.append(arrow_table)` once |
| `test_asset_bts_on_time_partition_resolution` | `MonthlyPartitionsDefinition(start_date='2024-01-01')` resolves `'2024-01'` → `(year=2024, month=1)` passed to `BTSResource.download_month` |
| `test_asset_bts_on_time_no_op_on_zero_rows` | empty fixture → no `create_table`, no `append`, no raise |

### dbt model file-content tests (`tests/test_dbt_models.py`)

| Test | Asserts |
|------|---------|
| `test_stg_bts_inner_joins_dim_airport_and_dim_carrier` | both joins present in `stg_bts_on_time.sql` |
| `test_stg_bts_filters_empty_codes` | `NULLIF(...) IS NOT NULL` clauses present |
| `test_cancellation_marts_use_external_parquet` | parametrized over `agg_carrier_cancellations`, `agg_route_cancellations`: each declares `config(location=...)` |
| `test_cancellation_marts_have_required_columns` | parametrized: `cancellation_rate`, `total_scheduled`, `cancelled`, `period_start`, `period_end` aliased |
| `test_cancellation_rate_uses_nullif_count_pattern` | `NULLIF(COUNT(*), 0)` present |
| `test_dbt_seeds_present` | `dim_airport.csv` and `dim_carrier.csv` exist under `transforms/seeds/`, ICAO is first column |
| `test_dbt_project_configures_seeds` | `dbt_project.yml` has `seeds:` block with `+quote_columns: false` |

### Integration (`tests/integration/`)

| Test | Asserts |
|------|---------|
| `test_integration_dbt_build` (existing, modify) | dbt seed step succeeds; cancellation marts land at `s3://raw-flights/warehouse/marts/`; row count > 0; `cancellation_rate` non-null |
| `test_integration_iceberg_bts` (new) | `BTSResource(bts_fixture_file=...)` + `bts_on_time` against real Nessie + SeaweedFS: round-trip via PyIceberg, schema matches, partition `year_month` populated |
| `test_integration_bts_download` (new, gated) | `pytest.skipif(not os.getenv('TRAVELPAL_BTS_LIVE'))` — real `transtats.bts.gov` POST, asserts 200, ZIP magic bytes, ≥100k rows |
| `test_integration_e2e_with_bts_stub` (extend existing E2E) | stub mode runs full pipeline → marts → frontend exports; both `carrier_cancellations.parquet` and `route_cancellations.parquet` written |

### Frontend (`CancellationSection.test.tsx`)

| Test | Asserts |
|------|---------|
| `shows loading state` | both queries pending → `aria-busy` |
| `shows empty-state on zero rows` | `[]` from queries → "No cancellation data" copy |
| `shows error on rejected query` | rejected promise → `role="alert"` |
| `renders carrier bar with top 10 sorted by cancellation_rate desc` | mock 15 carriers → top 10 in DOM order, sorted desc |
| `renders route bar with top 10 routes` | route axis label = `ORIGIN → DEST` |
| `formats rate as percent` | rate `0.0123` → `1.2%` in tooltip/label |

Highcharts unit-tested via `<HighchartsReact />` `options` prop — assert `series[].data` shape, not chart internals.

### E2E (`frontend/tests/e2e/smoke.spec.ts`)

| Assertion |
|-----------|
| Cancellation section heading visible |
| Carrier bar `<svg>` has ≥1 bar |
| Route bar `<svg>` has ≥1 bar |
| No console errors |

### Coverage target

≥80% (Phase 0 currently 96%; Phase 1 additions expected ≥90%).

---

## 6. Risks & Open Questions

### R1 — BTS download stability

`transtats.bts.gov` has no SLA. **Mitigation:** Dagster retry policy (3 attempts, exp backoff). Live-download test gated behind `TRAVELPAL_BTS_LIVE=1` so CI never hits BTS. Also cache downloaded ZIPs in SeaweedFS (`bts_raw/{year_month}.zip`); asset checks SeaweedFS first.

### R2 — IATA → ICAO mapping coverage

`stg_bts_on_time` uses INNER JOIN — unmappable rows drop silently. **Mitigation:** add a non-blocking `dbt test` asserting `count(stg_bts) / count(raw_bts) > 0.99` per month. Failure flags a dim_airport gap.

### R3 — OpenFlights `dim_carrier` staleness

`airlines.dat` last updated 2017. Misses Avelo, Breeze, recent renames. **Decision:** accept staleness; add manual override CSV only if ≥0.5% rows drop on a real month.

### R4 — Highcharts license drift

Free for personal/non-commercial only. **Mitigation:** `LICENSING.md` at repo root noting non-commercial use.

### R5 — Mart partition vs query-time filter

`agg_*_cancellations` marts hold all-airport rows; `frontend_exports._MART_AIRPORT_PREDICATE` (Phase 0 fix) trims to `airport_icao` at export. Same pattern, no new infra. Predicate map gains entries for the two new marts: `origin_icao = $airport` for both (carrier already groups by origin; routes departing from this airport).

### R6 — Dagster partition replay across schema changes

PyIceberg's `update_schema()` API used to add columns idempotently before append; mirrors Phase 0 `raw_flights` pattern.

### R7 — Time horizon mismatch on dashboard

OpenSky timeliness is yesterday-fresh; BTS cancellations lag 3 months. **Mitigation:** `period_start` / `period_end` columns on cancellation marts → caption "Cancellation data: {period_start} – {period_end} (BTS)" above the cancellation section.

### R8 — dbt seed compile time

80k-row `dim_airport.csv` compiles in ~2-3s. Acceptable. If it grows: switch to `+materialized: external` parquet seed.

### Resolved questions

| # | Question | Decision |
|---|----------|----------|
| Q1 | Cache BTS ZIPs in SeaweedFS? | Yes |
| Q2 | `dim_carrier` override layer? | No, defer until evidence |
| Q3 | `period_*` caption on cancellation section? | Yes |
| Q4 | Backfill horizon — how many BTS months on first ship? | 12 months |

---

## 7. Out of Scope (Tracked for Follow-up)

- F1.3 Competitor Comparison Matrix (uses `dim_carrier` from this spec).
- F1.4 Temporal Bottleneck Heatmap.
- sqlglot ANSI → DuckDB transpilation.
- Adding cancellation metrics to `agg_daily_timeliness` / `agg_route_timeliness` (cross-source join with OpenSky).
- Real-time cancellation feed (would require commercial API).
- Non-US airport coverage (BTS is US-only).
