---
name: travelpal-dbt-duckdb
description: Use when writing, editing, or reviewing dbt models in the TravelPal transform layer (`pipeline/transforms/`), including staging, intermediate, or mart SQL files. Use when debugging NULL propagation in `is_on_time` or `on_time_ratio`. Use when adding new aggregation models or metrics to the route/daily timeliness marts. Use when verifying DuckDB dialect compatibility. Use when running or interpreting `dbt test` results for the transforms layer.
---

# TravelPal dbt + DuckDB Conventions

## Model Layout

```
pipeline/transforms/models/
├── staging/          stg_*  — clean raw source, convert types
├── intermediate/     fct_*  — per-flight metrics, route medians
└── marts/            agg_*  — grouped aggregations for downstream use
```

Run tests with:

```bash
dbt test --project-dir transforms
```

## Staging Layer

### Timestamp conversion

Always convert raw Unix integers at the staging boundary. Do not leave epoch integers in downstream models.

```sql
TO_TIMESTAMP(first_seen) AS departed_at,
TO_TIMESTAMP(last_seen)  AS arrived_at
```

`CAST(ts AS DATE)` is allowed for date extraction in downstream models.

## Intermediate Layer

### Route median — `fct_flight_performance.sql`

Use `PERCENTILE_CONT` directly in DuckDB. This is not ANSI SQL but is explicitly allowed for this project.

```sql
WITH route_medians AS (
    SELECT
        origin_icao,
        destination_icao,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY block_minutes) AS median_block_minutes
    FROM all_flights
    GROUP BY origin_icao, destination_icao
)
```

### NULL-safe `is_on_time` flag

Both operands must be checked before comparing. A NULL `block_minutes` means the flight has no timing data and must not be classified as late.

```sql
CASE
    WHEN f.block_minutes IS NULL OR m.median_block_minutes IS NULL THEN NULL
    WHEN f.block_minutes - m.median_block_minutes <= 15 THEN TRUE
    ELSE FALSE
END AS is_on_time
```

### `delay_minutes` — emit here, consume downstream

```sql
ROUND(f.block_minutes - m.median_block_minutes, 1) AS delay_minutes
```

Mart models read `delay_minutes` directly from `fct_flight_performance`. Do not recompute medians in aggregation models.

## Mart Layer

### NULL-safe `on_time_ratio` denominator (CRITICAL)

The denominator must exclude flights where `is_on_time IS NULL`. Using `COUNT(*)` or `SUM(CASE WHEN is_on_time THEN 1 ELSE 0 END)` treats NULL as FALSE and inflates the denominator.

**Correct:**

```sql
ROUND(
    COUNT(CASE WHEN is_on_time = TRUE THEN 1 END) * 1.0
    / NULLIF(COUNT(CASE WHEN is_on_time IS NOT NULL THEN 1 END), 0),
    3
) AS on_time_ratio
```

**Wrong — do not use:**

```sql
-- Treats NULL is_on_time as FALSE; inflates denominator
SUM(CASE WHEN is_on_time THEN 1 ELSE 0 END) / COUNT(*)
```

When all flights in a group have `is_on_time IS NULL`, `on_time_ratio` must be `NULL`, not `0`.

## Out-of-Scope Metrics

**No cancellation rate.** OpenSky only records completed flights. `is_cancelled` is always FALSE for this data source. Do not add `cancellation_rate` or any cancelled-flight logic. This is deferred to Phase 1 with a different source.

## SQL Dialect

Models are written directly in DuckDB dialect (Phase 0 ships a single engine). The sqlglot transpiler has been removed. If a second SQL engine (ClickHouse, Trino) is added in a future phase, the transpiler pattern can be reintroduced then.

- Do not introduce Trino-only or Spark-only syntax.

**DuckDB extensions used in models:**

| Function / syntax | Purpose |
|---|---|
| `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ...)` | Route median computation |
| `TO_TIMESTAMP(unix_int)` | Epoch-to-timestamp conversion |
| `CAST(ts AS DATE)` | Date extraction |

## Testing Checklist

- NULL propagation: when `block_minutes` is NULL, `is_on_time` must be NULL (not FALSE).
- `on_time_ratio` is NULL (not 0) when all flights in a group have NULL `is_on_time`.
- Aggregation models do not recompute medians — they consume `delay_minutes` from `fct_flight_performance`.
- Integration tests must provide a `profiles.yml` pointing `path` at the `tmp_path` DuckDB file.
