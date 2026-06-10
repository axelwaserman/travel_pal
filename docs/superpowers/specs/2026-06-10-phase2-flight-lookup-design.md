# Phase 2.3 — Flight Lookup Deepening Design

**Date:** 2026-06-10
**Branch:** `phase2/flight-lookup`
**Status:** Approved (Pre-Code Gate complete)

## Goal

Turn the existing `FlightLookup` section (input → result cards) into a real research tool:

- **Two-step search UX** — pick **Airports** or **Carriers** tab, then search within scope
- **Sort + filter** — on-time / delay / volume / volatility sort, min-flights slider 1–1000
- **Results bar chart** — Highcharts column of result on-time ratios above the result list
- **Drill-down side panel** — click a result → 440px panel slides in with daily timeliness, carrier breakdown, cancellation reason mix for that specific route
- **IATA / ICAO / name input** — accepts 2-letter (carrier IATA), 3-letter (airport IATA, carrier ICAO), 4-letter (airport ICAO), or substring of `name`

## Architecture

Two-step search avoids fan-out joins in DuckDB-WASM. Airport tab queries `route_timeliness.parquet` joined to `dim_airport.parquet`. Carrier tab queries `agg_carrier_cancellations.parquet` joined to `dim_carrier.parquet`. Two new dbt marts (`agg_carrier_route_cancellations`, `agg_route_cancellation_reasons`) feed the drill-down. `dim_airport.parquet` and `dim_carrier.parquet` join the existing `frontend_exports` asset alongside the four mart parquets.

URL state holds tab, search term, sort, filter, and open route — shareable, back-button-friendly. Side panel renders inside the section (no portal), uses focus trap + Escape + click-outside + X button.

## Components / file changes

```
pipeline/
  transforms/models/marts/
    agg_carrier_route_cancellations.sql      (new)
    agg_route_cancellation_reasons.sql       (new)
  transforms/models/marts/schema.yml         (modify — add tests for both)
  pipeline/assets/frontend_exports.py        (modify — extend _MARTS, _EXPORT_KEYS, _MART_AIRPORT_PREDICATE; dim parquets are airport-agnostic — single copy at frontend-exports root, not per-airport)

frontend/src/
  components/FlightLookup/
    FlightLookup.tsx                          (modify — tabs + sort + filter + bar chart + drill click)
    FlightLookup.css                          (modify — tabs, slider, panel positioning)
    FlightLookup.test.tsx                     (modify — tab switch, sort, filter, drill open)
    SearchTabs.tsx                            (new — Airports / Carriers radiogroup)
    SortBar.tsx                               (new — 4-option sort select + direction toggle)
    MinFlightsSlider.tsx                      (new — range 1..1000, debounced 300ms)
    ResultsBar.tsx                            (new — lazy Highcharts column of result on-time ratios, top 30)
    RoutePanel.tsx                            (new — side panel container, focus trap, close handlers, Promise.allSettled queries — one panel section can fail without taking down the others)
    RoutePanel.css                            (new — slide-in transform, mobile full-width)
    RoutePanelDailySparkline.tsx              (new — lazy Highcharts spline of daily on-time%)
    RoutePanelCarrierBreakdown.tsx            (new — lazy Highcharts bar of carrier × cancellation rate for route)
    RoutePanelReasonMix.tsx                   (new — lazy Highcharts column of A/B/C/D cancellation codes)
  db/queries.ts                                (modify — new query functions; see "Data flow")
  db/schemas.ts                                (modify — add 4 new schemas; see "Schemas")
  hooks/useSearchParams.ts                     (new — typed wrapper around URLSearchParams)
  hooks/useEscape.ts                           (new — bind Escape → callback)
  hooks/useClickOutside.ts                     (new — bind outside click → callback)
```

## Data flow

```
User types "KLAX" → SearchTabs ("airports") + searchTerm → queryAirportSearch
  → DuckDB-WASM SELECT FROM read_parquet(route_timeliness)
       JOIN read_parquet(dim_airport) AS o ON o.icao = origin_icao
       JOIN read_parquet(dim_airport) AS d ON d.icao = destination_icao
       WHERE upper(o.icao) LIKE $1 OR upper(o.iata) LIKE $1 OR upper(o.name) LIKE $1
          OR upper(d.icao) LIKE $1 OR upper(d.iata) LIKE $1 OR upper(d.name) LIKE $1
       LIMIT 200
  → parsePartial(RouteTimelinessWithAirportNameSchema)
  → setResults state
  → ResultsBar receives sorted+filtered slice (top 30), filters out rows with null on_time_ratio (same pattern as CarrierBar in P2.2), renders Highcharts column
  → results map → ResultCard list with onClick

User clicks ResultCard → setOpenRoute({origin, destination}) + URL ?route=KJFK-KLAX
  → RoutePanel mounts, parallel queries via Promise.allSettled:
       queryRouteDaily(origin, dest)        → spline of last-365-day on-time ratios
       queryRouteCarriers(origin, dest)     → bar by carrier × cancellation_rate
       queryRouteReasons(origin, dest)      → column of A/B/C/D cancellation codes
  → focus moves to panel close button (focus trap active)
  → backdrop click / Escape / X button → setOpenRoute(null), URL cleared, focus restored

User drags MinFlightsSlider → debounced 300ms → URL ?min=250 → results re-filtered client-side
User changes SortBar → URL ?sort=delay_asc → results re-sorted client-side
```

Sort and filter are pure client-side reactivity — no re-query when sort/filter change. New query only when search term, tab, or open route changes.

### URL state

```
?tab=airports|carriers
&q=KLAX            (search term, alphanumeric+space+hyphen for carrier names; alphanumeric only for airports)
&sort=on_time_desc|on_time_asc|delay_asc|delay_desc|volume_desc|volume_asc|volatility_asc
&min=100           (min flights threshold, integer 1..1000)
&route=KJFK-KLAX   (drill panel open; cleared on close)
```

Defaults: `tab=airports`, `sort=on_time_desc`, `min=1`. Empty `q` → no query, empty results pane.

### Query function signatures

```ts
queryAirportSearch(airportIcao: string, term: string): Promise<RouteTimelinessWithAirportName[]>
queryCarrierSearch(airportIcao: string, term: string): Promise<CarrierCancellationWithName[]>
queryRouteDaily(originIcao: string, destinationIcao: string): Promise<DailyTimeliness[]>
queryRouteCarriers(originIcao: string, destinationIcao: string): Promise<CarrierRouteCancellation[]>
queryRouteReasons(originIcao: string, destinationIcao: string): Promise<RouteCancellationReason[]>
```

`queryAirportSearch` replaces `queryFlightLookup`. `LIMIT 200` for airport tab, `LIMIT 50` for carrier tab. Bar chart capped to top 30 to avoid Highcharts choke.

## New marts

### `agg_carrier_route_cancellations.sql`

```sql
{{ config(
    materialized='external',
    location="s3://" ~ env_var('RAW_BUCKET', 'raw-flights') ~ "/warehouse/marts/" ~ this.name ~ ".parquet"
) }}
SELECT
    origin_icao,
    destination_icao,
    carrier_icao,
    MAX(carrier_name)                                   AS carrier_name,
    COUNT(*)                                            AS total_scheduled,
    SUM(CASE WHEN cancelled THEN 1 ELSE 0 END)          AS cancelled,
    ROUND(
        SUM(CASE WHEN cancelled THEN 1 ELSE 0 END) * 1.0
            / NULLIF(COUNT(*), 0),
        4
    )                                                   AS cancellation_rate,
    MIN(flight_date)                                    AS period_start,
    MAX(flight_date)                                    AS period_end
FROM {{ ref('stg_bts_on_time') }}
GROUP BY origin_icao, destination_icao, carrier_icao
```

**Grain:** (origin, dest, carrier). Drives RoutePanelCarrierBreakdown.

### `agg_route_cancellation_reasons.sql`

BTS `cancellation_code` legend:
- A = Air Carrier
- B = Weather
- C = National Air System
- D = Security
- (NULL / "" when not cancelled)

```sql
{{ config(
    materialized='external',
    location="s3://" ~ env_var('RAW_BUCKET', 'raw-flights') ~ "/warehouse/marts/" ~ this.name ~ ".parquet"
) }}
WITH base AS (
    SELECT
        origin_icao,
        destination_icao,
        CASE
            WHEN cancellation_code = 'A' THEN 'Air Carrier'
            WHEN cancellation_code = 'B' THEN 'Weather'
            WHEN cancellation_code = 'C' THEN 'National Air System'
            WHEN cancellation_code = 'D' THEN 'Security'
            ELSE 'Other / Unknown'
        END AS reason
    FROM {{ ref('stg_bts_on_time') }}
    WHERE cancelled = TRUE
      AND NULLIF(cancellation_code, '') IS NOT NULL
)
SELECT
    origin_icao,
    destination_icao,
    reason,
    COUNT(*)                                                    AS cancelled_count,
    ROUND(
        COUNT(*) * 1.0
            / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY origin_icao, destination_icao), 0),
        4
    )                                                           AS reason_share
FROM base
GROUP BY origin_icao, destination_icao, reason
```

**Grain:** (origin, dest, reason). `reason_share` per-route ratio summing to 1.0.

### dbt schema.yml additions

```yaml
- name: agg_carrier_route_cancellations
  columns:
    - name: origin_icao
      tests: [not_null]
    - name: destination_icao
      tests: [not_null]
    - name: carrier_icao
      tests: [not_null]
    - name: total_scheduled
      tests: [not_null]
    - name: cancelled
      tests: [not_null]

- name: agg_route_cancellation_reasons
  columns:
    - name: origin_icao
      tests: [not_null]
    - name: destination_icao
      tests: [not_null]
    - name: reason
      tests:
        - not_null
        - accepted_values:
            values: ['Air Carrier', 'Weather', 'National Air System', 'Security', 'Other / Unknown']
    - name: cancelled_count
      tests: [not_null]
```

### `frontend_exports.py` extension

Add to `_MARTS`:
```py
"agg_carrier_route_cancellations": "agg_carrier_route_cancellations",
"agg_route_cancellation_reasons": "agg_route_cancellation_reasons",
"dim_airport": "dim_airport",
"dim_carrier": "dim_carrier",
```

`_EXPORT_KEYS` (note: dim parquets at root, not per-airport, since they're shared across airports):
```py
"agg_carrier_route_cancellations": "carrier_route_cancellations.parquet",
"agg_route_cancellation_reasons": "route_cancellation_reasons.parquet",
"dim_airport": "../dim_airport.parquet",      # one level up from /{AIRPORT}/
"dim_carrier": "../dim_carrier.parquet",
```

`_MART_AIRPORT_PREDICATE`:
```py
"agg_carrier_route_cancellations": "origin_icao = $airport OR destination_icao = $airport",
"agg_route_cancellation_reasons":  "origin_icao = $airport OR destination_icao = $airport",
"dim_airport": None,        # full table, no airport scope
"dim_carrier": None,        # full table
```

`None` predicate handled by skipping the WHERE clause (~85K airports + ~5K carriers; gzipped ≈ 4 MB total).

### Schemas (`frontend/src/db/schemas.ts` additions)

```ts
export const RouteTimelinessWithAirportNameSchema = RouteTimelinessSchema.extend({
  origin_name: z.string(),
  destination_name: z.string(),
})
export type RouteTimelinessWithAirportName = z.infer<typeof RouteTimelinessWithAirportNameSchema>

export const CarrierCancellationWithNameSchema = CarrierCancellationSchema
// (carrier_name already present; alias kept for parallel naming with airport version)
export type CarrierCancellationWithName = z.infer<typeof CarrierCancellationWithNameSchema>

export const CarrierRouteCancellationSchema = z.object({
  origin_icao: z.string(),
  destination_icao: z.string(),
  carrier_icao: z.string(),
  carrier_name: z.string(),
  total_scheduled: NUMERIC_FIELD,
  cancelled: NUMERIC_FIELD,
  cancellation_rate: NULLABLE_NUMERIC,
  period_start: DATE_FIELD,
  period_end: DATE_FIELD,
})
export type CarrierRouteCancellation = z.infer<typeof CarrierRouteCancellationSchema>

export const RouteCancellationReasonSchema = z.object({
  origin_icao: z.string(),
  destination_icao: z.string(),
  reason: z.enum(['Air Carrier', 'Weather', 'National Air System', 'Security', 'Other / Unknown']),
  cancelled_count: NUMERIC_FIELD,
  reason_share: NULLABLE_NUMERIC,
})
export type RouteCancellationReason = z.infer<typeof RouteCancellationReasonSchema>
```

`DATE_FIELD` constant added if not yet extracted (refactor from inline `z.union([z.coerce.number(), z.string(), z.date()])` duplicated across CarrierCancellation + RouteCancellation per P2.2 quality review).

## Error handling

| Source | Failure mode | Behavior |
|---|---|---|
| `queryAirportSearch` / `queryCarrierSearch` | Parquet 404 (pipeline never ran) | `console.error`; setError("Failed to load. Run the pipeline (`just run-pipeline`)."); results stay empty |
| `parsePartial` partial drop | Schema drift | Existing P2.2 `console.warn`; valid subset rendered |
| `parsePartial` total drop | All rows fail validation | Empty results + `console.warn`; UI shows "No routes found" empty state |
| `queryRouteDaily/Carriers/Reasons` | One panel query fails | Per-section in-panel error: "Couldn't load daily timeliness." Other two panels still render. Isolated by `Promise.allSettled`. |
| Drill panel opens with invalid `?route=XXX-YYY` | ICAO not in dim, or no rows | Panel shows "Route not found" + close button. URL stays so refresh idempotent. |
| Min-flights slider exceeds dataset | All filtered out | Empty-state #3: "0 of N results meet ≥M flights threshold. Lower the slider." |
| Highcharts dynamic import fails | Already covered by P2.2 `<Suspense>` | Spinner stays; user retries via refresh |
| Search input contains SQL chars | Sanitization regex strips | Airport tab: `/[^A-Z0-9]/gi`. Carrier tab: `/[^A-Z0-9 -]/gi` (allow spaces + hyphens for "Air France" / "JetBlue"). |

### Empty states

- Empty `q` → "Type an airport (KJFK / JFK) or carrier (DAL / Delta) to begin."
- Non-empty `q`, 0 matches → "No routes found for `<term>`. Try a different ICAO/IATA code or carrier name."
- 0 matches after `min` filter → "0 of <N> results meet ≥<M> flights threshold. Lower the slider."
- Drill panel: "No cancellations recorded for this route in 2024." when reason mix empty. Same for daily timeliness if route only flies a few days.

### Mobile (< 768px)

- Side panel slides full-width instead of 440px
- Result cards stack vertically
- ResultsBar full-width above list
- Sort + filter collapse into a `<details>` summary

## Testing

### Unit (vitest)
- `useSearchParams` — tab/sort/min/route round-trip
- `useEscape` / `useClickOutside` — bind/unbind, callback fires once
- `MinFlightsSlider` — 300ms debounce, edge values 1 / 1000
- `SortBar` — direction toggle, default value
- `SearchTabs` — keyboard nav (arrow keys), active state
- `RoutePanel` — focus trap on open, focus restore on close, Escape, click-outside
- `parsePartial` for new schemas (extend `queries.test.ts`)
- New query functions with stub `getDb()` returning typed Arrow arrays
- `FlightLookup` — tab switch resets results, sort + filter applied, drill click opens panel, panel close clears `?route`

### Integration (pytest)
- `test_dbt_models.py` — both new marts produce non-zero rows against fixture
- `test_asset_frontend_exports.py` — 6 parquets land in S3 (4 marts + 2 dims) per airport scope; dim parquets at root level, not per-airport

### E2E (Playwright)
- Extend `smoke.spec.ts`: type "JFK", switch to Carriers tab, expect ≥1 carrier card, click first card, expect side panel with 3 child sections, Escape → panel closes, URL `?route=` cleared
- Extend `uat-snapshot.spec.ts`: full-page screenshot after search + drill, dump panel innerText

### Performance
- Bundle: no new chunk over 50 KB gzip (Highcharts already shared from P2.2)
- Initial route load (`/`) untouched — flight lookup queries only fire after user input
- Drill panel queries via `Promise.allSettled`
- Min-flights slider debounced 300ms

## Out of scope

- Multi-airport selector (P2.4)
- Authenticated saved searches / favorites
- Route-to-route comparison (multi-select drill)
- Real-time / live data (Phase 3+)
- Map visualization (separate phase)
- IATA disambiguation when input matches multiple — display all matches, user picks
- Airport autocomplete dropdown — post-launch if user feedback demands
- Carrier search across `flight_number` (not in marts; would need raw_flights join)
