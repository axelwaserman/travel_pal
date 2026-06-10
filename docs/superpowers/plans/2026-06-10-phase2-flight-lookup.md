# Phase 2.3 — Flight Lookup Deepening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Each task runs in its own isolated git worktree off `phase2/flight-lookup`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two-step search (Airports / Carriers tab), sort + min-flights filter, results bar chart, drill-down side panel with daily timeliness + carrier breakdown + cancellation reason mix. Backed by 2 new dbt marts and dim tables exported to S3.

**Architecture:** See `docs/superpowers/specs/2026-06-10-phase2-flight-lookup-design.md`. Pure client-side reactivity for sort/filter; URL params for shareable state; lazy Highcharts (chunk already exists from P2.2).

**Tech Stack:** dbt-duckdb, PyIceberg, React 18, TypeScript, vite, Highcharts 11 (lazy), zod 4, vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-06-10-phase2-flight-lookup-design.md`

---

## Task 1: New dbt marts (carrier_route + reason_mix) + tests

**Files:**
- Create: `pipeline/transforms/models/marts/agg_carrier_route_cancellations.sql`
- Create: `pipeline/transforms/models/marts/agg_route_cancellation_reasons.sql`
- Modify: `pipeline/transforms/models/marts/schema.yml`
- Modify: `pipeline/tests/test_dbt_models.py`

- [ ] **Step 1: Write the failing pytest assertions**

Add two test functions to `pipeline/tests/test_dbt_models.py` asserting both new marts produce non-zero rows + expected columns against the existing fixture. Look at the existing pattern (e.g. `test_agg_carrier_cancellations_mart_has_rows`) and copy the shape.

Run: `cd pipeline && uv run pytest tests/test_dbt_models.py -v -k "carrier_route or reason"`
Expected: FAIL with "model not found" / "no such file".

- [ ] **Step 2: Implement `agg_carrier_route_cancellations.sql`**

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

- [ ] **Step 3: Implement `agg_route_cancellation_reasons.sql`**

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

- [ ] **Step 4: Add schema tests**

Append to `pipeline/transforms/models/marts/schema.yml`:

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

- [ ] **Step 5: Run dbt build against integration fixture**

```bash
cd /Users/axel/code/travel_pal && just init-buckets && just materialize-bts 2024-01-01
docker compose exec dagster-webserver bash -c "cd /opt/dagster/app/transforms && dbt build --target dev"
```

Expected: 13 models built (was 11), tests pass.

- [ ] **Step 6: Run pytest**

```bash
cd pipeline && uv run pytest tests/test_dbt_models.py -v --tb=short
```

Expected: all PASS including the two new mart tests.

- [ ] **Step 7: Commit**

```bash
git add pipeline/transforms/models/marts/agg_carrier_route_cancellations.sql \
        pipeline/transforms/models/marts/agg_route_cancellation_reasons.sql \
        pipeline/transforms/models/marts/schema.yml \
        pipeline/tests/test_dbt_models.py
git commit -m "feat(dbt): agg_carrier_route_cancellations + agg_route_cancellation_reasons

Two new marts feeding the P2.3 flight-lookup drill-down panel:

- agg_carrier_route_cancellations: per (origin, dest, carrier)
  cancellation rate from BTS On-Time data.
- agg_route_cancellation_reasons: per (origin, dest, reason)
  share of cancellations by BTS cancellation_code (A=Carrier,
  B=Weather, C=NAS, D=Security, else Other / Unknown).

Both materialize as external parquets in raw-flights/warehouse/marts/.
Schema tests cover not_null constraints on grain columns + accepted
values on the reason enum."
```

---

## Task 2: `frontend_exports` asset emits dim_airport, dim_carrier, 2 new marts

**Files:**
- Modify: `pipeline/pipeline/assets/frontend_exports.py`
- Modify: `pipeline/tests/test_asset_frontend_exports.py` (or wherever the asset is tested)

- [ ] **Step 1: Write the failing test**

Extend the existing frontend_exports asset test to assert 6 parquets land in S3 (4 marts + 2 dims). Dim parquets are airport-agnostic — they should land at `frontend-exports/dim_airport.parquet` (root level), not under `frontend-exports/{AIRPORT_ICAO}/`.

```bash
cd pipeline && uv run pytest tests/test_asset_frontend_exports.py -v --tb=short
```

Expected: FAIL because dims aren't in `_MARTS` / `_EXPORT_KEYS` yet.

- [ ] **Step 2: Extend the asset's mart maps**

Modify `pipeline/pipeline/assets/frontend_exports.py`. Add to `_MARTS`:

```py
"agg_carrier_route_cancellations": "agg_carrier_route_cancellations",
"agg_route_cancellation_reasons": "agg_route_cancellation_reasons",
"dim_airport": "main_ref.dim_airport",   # dbt seed in main_ref schema
"dim_carrier": "main_ref.dim_carrier",
```

`_EXPORT_KEYS`:

```py
"agg_carrier_route_cancellations": "carrier_route_cancellations.parquet",
"agg_route_cancellation_reasons": "route_cancellation_reasons.parquet",
"dim_airport": "../dim_airport.parquet",
"dim_carrier": "../dim_carrier.parquet",
```

`_MART_AIRPORT_PREDICATE`:

```py
"agg_carrier_route_cancellations": "origin_icao = $airport OR destination_icao = $airport",
"agg_route_cancellation_reasons": "origin_icao = $airport OR destination_icao = $airport",
"dim_airport": None,
"dim_carrier": None,
```

Update the loop body in the asset to: when predicate is `None`, skip the WHERE clause; when key starts with `../`, write to the bucket root instead of `{airport}/`.

- [ ] **Step 3: Run pytest**

Expected: PASS.

- [ ] **Step 4: Re-run pipeline end-to-end against live stack**

```bash
cd /Users/axel/code/travel_pal && just run-pipeline
just ls-exports
```

Expected: 4 parquets under `frontend-exports/KJFK/` (route_timeliness, daily_timeliness, carrier_cancellations, route_cancellations) **plus** the 2 new ones (carrier_route_cancellations, route_cancellation_reasons), AND 2 root-level parquets (dim_airport, dim_carrier). Verify dim parquet sizes are sensible (airport ~3 MB raw, carrier ~150 KB).

```bash
AWS_ACCESS_KEY_ID=admin AWS_SECRET_ACCESS_KEY=admin \
  aws s3 ls s3://frontend-exports/ --endpoint-url http://localhost:8333
```

Should show `dim_airport.parquet`, `dim_carrier.parquet`, `KJFK/`.

- [ ] **Step 5: Commit**

```bash
git add pipeline/pipeline/assets/frontend_exports.py \
        pipeline/tests/test_asset_frontend_exports.py
git commit -m "feat(pipeline): frontend_exports emits dim_airport + dim_carrier + 2 P2.3 marts

Adds four new entries to the frontend_exports asset:
- agg_carrier_route_cancellations (per-airport)
- agg_route_cancellation_reasons (per-airport)
- dim_airport (root-level, airport-agnostic)
- dim_carrier (root-level, airport-agnostic)

Predicate=None signals 'no airport filter; export full table'.
Key prefix '../' writes to the bucket root rather than per-airport
prefix, so the dim parquets are shared across airports (P2.4 ready)."
```

---

## Task 3: Schemas (`schemas.ts`) + new query functions (`queries.ts`)

**Files:**
- Modify: `frontend/src/db/schemas.ts`
- Modify: `frontend/src/db/queries.ts`
- Modify: `frontend/src/db/queries.test.ts`
- Modify: `frontend/src/db/client.ts` (only if `SEAWEEDFS_PUBLIC_BASE` needs a sibling for root-level parquets)

- [ ] **Step 1: Add new schemas**

In `frontend/src/db/schemas.ts`, after the existing schemas:

```ts
// Extract the period_start / period_end union to a shared constant — caught
// in P2.2 quality review as DRY violation, fixing it here.
const DATE_FIELD = z.union([z.coerce.number(), z.string(), z.date()])

export const RouteTimelinessWithAirportNameSchema = RouteTimelinessSchema.extend({
  origin_name: z.string(),
  destination_name: z.string(),
})
export type RouteTimelinessWithAirportName = z.infer<typeof RouteTimelinessWithAirportNameSchema>

// Alias kept for parallel naming with airport version; carrier_name already
// present in CarrierCancellationSchema.
export const CarrierCancellationWithNameSchema = CarrierCancellationSchema
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

Also refactor `CarrierCancellationSchema` and `RouteCancellationSchema` to use the new `DATE_FIELD` constant for `period_start` / `period_end`.

- [ ] **Step 2: Write failing tests for new query functions**

Extend `frontend/src/db/queries.test.ts` with stub tests for `queryAirportSearch`, `queryCarrierSearch`, `queryRouteDaily`, `queryRouteCarriers`, `queryRouteReasons`. Each test mocks `getDb()` to return a fake connection that resolves with a typed Arrow array.

```bash
cd frontend && npm run test:unit -- queries
```

Expected: FAIL with "function not exported".

- [ ] **Step 3: Implement query functions in `queries.ts`**

```ts
// New SEAWEEDFS_PUBLIC_BASE_ROOT exported from client.ts:
//   `${SEAWEEDFS_PUBLIC_BASE.replace(/\/$/, '')}/..` — points at the bucket root.
// Use it for dim_airport.parquet and dim_carrier.parquet which are not per-airport.

// queryAirportSearch:
const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/route_timeliness.parquet`
const dimUrl = `${SEAWEEDFS_PUBLIC_BASE_ROOT}/dim_airport.parquet`
const sanitized = term.replace(/[^A-Za-z0-9]/g, '').toUpperCase()
const like = `%${sanitized}%`
const stmt = await conn.prepare(
  `SELECT
       r.*,
       o.name AS origin_name,
       d.name AS destination_name
   FROM read_parquet('${url}') AS r
   JOIN read_parquet('${dimUrl}') AS o ON o.icao = r.origin_icao
   JOIN read_parquet('${dimUrl}') AS d ON d.icao = r.destination_icao
   WHERE upper(o.icao) LIKE $1 OR upper(o.iata) LIKE $1 OR upper(o.name) LIKE $1
      OR upper(d.icao) LIKE $1 OR upper(d.iata) LIKE $1 OR upper(d.name) LIKE $1
   LIMIT 200`
)
const result = await stmt.query(like)
return parsePartial(RouteTimelinessWithAirportNameSchema, result.toArray().map(r => r.toJSON()), 'queryAirportSearch')
```

`queryCarrierSearch` follows the same pattern using `agg_carrier_cancellations.parquet` + `dim_carrier.parquet` and the relaxed regex `/[^A-Za-z0-9 -]/gi`. `LIMIT 50`.

`queryRouteDaily` reads `daily_timeliness.parquet`, filters where `origin_icao = $1` AND a join to derive destination from the route param. (Daily mart is per-airport but rows are origin-only — see whether `flight_lookup_route_id` columns are needed; for now, filter by both origin AND destination since the daily_timeliness table includes both columns.)

`queryRouteCarriers` reads `carrier_route_cancellations.parquet`, filters origin+dest.

`queryRouteReasons` reads `route_cancellation_reasons.parquet`, filters origin+dest.

`SEAWEEDFS_PUBLIC_BASE_ROOT` exported alongside `SEAWEEDFS_PUBLIC_BASE` from `client.ts`:

```ts
export const SEAWEEDFS_PUBLIC_BASE_ROOT =
  import.meta.env.VITE_SEAWEEDFS_PUBLIC_BASE_ROOT ?? 'http://localhost:8333/frontend-exports'
```

- [ ] **Step 4: Run vitest + tsc + eslint**

```bash
cd frontend && npm run test:unit && npx tsc --noEmit && npx eslint src tests
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/db/schemas.ts frontend/src/db/queries.ts frontend/src/db/queries.test.ts frontend/src/db/client.ts
git commit -m "feat(frontend): zod schemas + queries for P2.3 search + drill-down

Adds 4 new schemas (RouteTimelinessWithAirportName,
CarrierCancellationWithName, CarrierRouteCancellation,
RouteCancellationReason) and extracts the DATE_FIELD constant per the
P2.2 quality review.

Adds 5 new query functions:
- queryAirportSearch: route_timeliness JOIN dim_airport (LIMIT 200)
- queryCarrierSearch: agg_carrier_cancellations JOIN dim_carrier (LIMIT 50)
- queryRouteDaily/Carriers/Reasons: drill-down panel queries

SEAWEEDFS_PUBLIC_BASE_ROOT added for the airport-agnostic dim parquets."
```

---

## Task 4: Hooks — `useSearchParams`, `useEscape`, `useClickOutside`

**Files:**
- Create: `frontend/src/hooks/useSearchParams.ts`
- Create: `frontend/src/hooks/useEscape.ts`
- Create: `frontend/src/hooks/useClickOutside.ts`
- Create: `frontend/src/hooks/useSearchParams.test.ts`
- Create: `frontend/src/hooks/useEscape.test.ts`
- Create: `frontend/src/hooks/useClickOutside.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
// useSearchParams.test.ts — round-trip tab/sort/min/route through URLSearchParams
// useEscape.test.ts — fires callback on Escape, removes listener on unmount, no fire on other keys
// useClickOutside.test.ts — fires callback when click target is outside ref, no fire when inside
```

Run: `cd frontend && npm run test:unit -- hooks`
Expected: FAIL.

- [ ] **Step 2: Implement `useSearchParams`**

```ts
// useSearchParams.ts
import { useCallback, useEffect, useState } from 'react'

export type FlightLookupParams = {
  tab: 'airports' | 'carriers'
  q: string
  sort: 'on_time_desc' | 'on_time_asc' | 'delay_asc' | 'delay_desc' | 'volume_desc' | 'volume_asc' | 'volatility_asc'
  min: number
  route: string | null
}

const DEFAULT: FlightLookupParams = {
  tab: 'airports',
  q: '',
  sort: 'on_time_desc',
  min: 1,
  route: null,
}

function read(): FlightLookupParams {
  const sp = new URLSearchParams(window.location.search)
  return {
    tab: (sp.get('tab') === 'carriers' ? 'carriers' : 'airports'),
    q: sp.get('q') ?? '',
    sort: (sp.get('sort') ?? 'on_time_desc') as FlightLookupParams['sort'],
    min: Math.max(1, Math.min(1000, Number(sp.get('min') ?? 1))),
    route: sp.get('route'),
  }
}

function write(p: Partial<FlightLookupParams>) {
  const sp = new URLSearchParams(window.location.search)
  Object.entries(p).forEach(([k, v]) => {
    if (v == null || v === '' || (k === 'min' && v === 1) || (k === 'tab' && v === 'airports') || (k === 'sort' && v === 'on_time_desc')) {
      sp.delete(k)
    } else {
      sp.set(k, String(v))
    }
  })
  const next = sp.toString()
  const url = `${window.location.pathname}${next ? '?' + next : ''}`
  window.history.replaceState({}, '', url)
}

export function useFlightLookupParams() {
  const [params, setParams] = useState<FlightLookupParams>(read)
  useEffect(() => {
    const onPop = () => setParams(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  const update = useCallback((patch: Partial<FlightLookupParams>) => {
    write(patch)
    setParams(read())
  }, [])
  return [params, update] as const
}
```

- [ ] **Step 3: Implement `useEscape` + `useClickOutside`**

```ts
// useEscape.ts
import { useEffect } from 'react'
export function useEscape(callback: () => void, enabled = true) {
  useEffect(() => {
    if (!enabled) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') callback() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [callback, enabled])
}

// useClickOutside.ts
import { RefObject, useEffect } from 'react'
export function useClickOutside<T extends HTMLElement>(
  ref: RefObject<T>,
  callback: () => void,
  enabled = true,
) {
  useEffect(() => {
    if (!enabled) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) callback()
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [ref, callback, enabled])
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm run test:unit -- hooks
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/
git commit -m "feat(frontend): URL-state, Escape, click-outside hooks for P2.3

useFlightLookupParams: typed wrapper around URLSearchParams, defaults
elided from URL so canonical view stays clean. popstate sync.

useEscape / useClickOutside: small primitives for the side-panel close
behavior. Both gated by an enabled flag so RoutePanel can disable them
when the panel is not open."
```

---

## Task 5: SearchTabs + SortBar + MinFlightsSlider components

**Files:**
- Create: `frontend/src/components/FlightLookup/SearchTabs.tsx` + `.test.tsx`
- Create: `frontend/src/components/FlightLookup/SortBar.tsx` + `.test.tsx`
- Create: `frontend/src/components/FlightLookup/MinFlightsSlider.tsx` + `.test.tsx`
- Modify: `frontend/src/components/FlightLookup/FlightLookup.css`

- [ ] **Step 1: Write failing tests**

For each component:
- SearchTabs: renders 2 tabs, click switches active, arrow-key nav swaps focus.
- SortBar: 7 sort options in a `<select>` (or radiogroup), change fires `onChange` with new value.
- MinFlightsSlider: range input 1..1000, change fires `onChange` with new int after 300ms debounce.

- [ ] **Step 2: Implement each (one component per sub-task — keep PRs thin)**

Use existing CSS variables (--color-text, --color-accent, etc.). Tabs as ARIA `role="tablist"` / `role="tab"` with `aria-selected`. Slider as `<input type="range">` with `aria-valuemin/max/now`. Sort as `<select>` for keyboard simplicity.

- [ ] **Step 3: Run vitest + tsc + eslint**

```bash
cd frontend && npm run test:unit && npx tsc --noEmit && npx eslint src tests
```

Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/FlightLookup/SearchTabs.tsx \
        frontend/src/components/FlightLookup/SortBar.tsx \
        frontend/src/components/FlightLookup/MinFlightsSlider.tsx \
        frontend/src/components/FlightLookup/SearchTabs.test.tsx \
        frontend/src/components/FlightLookup/SortBar.test.tsx \
        frontend/src/components/FlightLookup/MinFlightsSlider.test.tsx \
        frontend/src/components/FlightLookup/FlightLookup.css
git commit -m "feat(frontend): SearchTabs + SortBar + MinFlightsSlider for P2.3

Three small UI primitives wired to the URL-state hook (controllers
in Task 7). All keyboard-accessible, all use existing design tokens.
Slider debounces onChange 300ms to avoid URL thrashing."
```

---

## Task 6: ResultsBar (lazy Highcharts column above results)

**Files:**
- Create: `frontend/src/components/FlightLookup/ResultsBar.tsx` + `.test.tsx`
- Modify: `frontend/src/components/FlightLookup/FlightLookup.tsx`

- [ ] **Step 1: Write failing test**

ResultsBar takes `results: RouteTimelinessWithAirportName[]` + `airportIcao`. Renders Highcharts column with x-axis = `${origin_icao} → ${destination_icao}`, y-axis = `on_time_ratio * 100`. Caps to top 30. Filters out null on_time_ratio rows.

- [ ] **Step 2: Implement**

Mirror P2.2 `CarrierBar` / `RouteBar` pattern: dynamic Highcharts import, named export, type predicate filter for non-null on_time_ratio.

- [ ] **Step 3: Wire into FlightLookup**

In `FlightLookup.tsx`, after the input row, render:

```tsx
{results.length > 0 && (
  <Suspense fallback={<ChartSpinner label="Loading results chart…" />}>
    <ResultsBar results={results} airportIcao={airportIcao} />
  </Suspense>
)}
```

- [ ] **Step 4: Verify bundle delta**

```bash
cd frontend && npm run build 2>&1 | grep -E "ResultsBar|highcharts|index-"
```

Expected: ResultsBar lands in its own ~1 KB chunk; no impact on initial bundle (Highcharts already shared).

- [ ] **Step 5: Run tests + commit**

```bash
cd frontend && npm run test:unit && npx tsc --noEmit
git add frontend/src/components/FlightLookup/ResultsBar.tsx \
        frontend/src/components/FlightLookup/ResultsBar.test.tsx \
        frontend/src/components/FlightLookup/FlightLookup.tsx
git commit -m "feat(frontend): ResultsBar — Highcharts column of route on-time ratios

Lazy-loaded; reuses the existing Highcharts chunk from P2.2.
Caps to top 30 rows and filters out null on_time_ratio (same
type-predicate pattern as CarrierBar in P2.2)."
```

---

## Task 7: Wire FlightLookup to URL state + tabs + sort + filter (no panel yet)

**Files:**
- Modify: `frontend/src/components/FlightLookup/FlightLookup.tsx`
- Modify: `frontend/src/components/FlightLookup/FlightLookup.test.tsx`

- [ ] **Step 1: Write failing tests**

- Switching tab clears results + updates URL ?tab=carriers
- Changing sort re-orders results without re-querying (mock query call count == 1 across 3 sort changes)
- Changing min slider filters client-side (mock query call count unchanged)

- [ ] **Step 2: Refactor `FlightLookup.tsx`**

Replace the current local `useState` for query/results with:
- `const [params, setParams] = useFlightLookupParams()`
- Trigger query in `useEffect([params.tab, params.q])` — only re-query when tab or term changes, never on sort/filter/route
- Use `params.sort` / `params.min` to derive the visible slice via `useMemo`

Clear results when tab changes. Reset min slider to 1 when tab changes (volume scales differ between airport and carrier views).

- [ ] **Step 3: Run tests + commit**

```bash
cd frontend && npm run test:unit && npx tsc --noEmit && npx eslint src tests
git add frontend/src/components/FlightLookup/FlightLookup.tsx \
        frontend/src/components/FlightLookup/FlightLookup.test.tsx
git commit -m "feat(frontend): tabs + sort + filter wired through URL state

FlightLookup now sources tab/q/sort/min/route from
useFlightLookupParams. Sort and min are pure client-side derivations
via useMemo; only tab and search term trigger new queries. Tab
switches clear results and reset the min slider to 1."
```

---

## Task 8: RoutePanel (side panel + drill-down sub-charts)

**Files:**
- Create: `frontend/src/components/FlightLookup/RoutePanel.tsx` + `.test.tsx`
- Create: `frontend/src/components/FlightLookup/RoutePanel.css`
- Create: `frontend/src/components/FlightLookup/RoutePanelDailySparkline.tsx`
- Create: `frontend/src/components/FlightLookup/RoutePanelCarrierBreakdown.tsx`
- Create: `frontend/src/components/FlightLookup/RoutePanelReasonMix.tsx`
- Modify: `frontend/src/components/FlightLookup/FlightLookup.tsx`

- [ ] **Step 1: Write failing tests for RoutePanel**

- Renders nothing when `route` prop is null
- When `route` set, mounts and runs 3 queries via `Promise.allSettled`
- Pressing Escape calls `onClose`
- Clicking outside (on backdrop) calls `onClose`
- Clicking the X button calls `onClose`
- Focus moves to close button on mount; restores to triggering element on close

- [ ] **Step 2: Implement RoutePanel**

```tsx
// RoutePanel.tsx
import { useEffect, useRef, useState } from 'react'
import { useEscape } from '../../hooks/useEscape'
import { useClickOutside } from '../../hooks/useClickOutside'
import {
  queryRouteDaily,
  queryRouteCarriers,
  queryRouteReasons,
  type DailyTimeliness,
  type CarrierRouteCancellation,
  type RouteCancellationReason,
} from '../../db/queries'
import { RoutePanelDailySparkline } from './RoutePanelDailySparkline'
import { RoutePanelCarrierBreakdown } from './RoutePanelCarrierBreakdown'
import { RoutePanelReasonMix } from './RoutePanelReasonMix'

interface Props {
  origin: string
  destination: string
  onClose: () => void
}

interface PanelState {
  daily: DailyTimeliness[] | { error: string }
  carriers: CarrierRouteCancellation[] | { error: string }
  reasons: RouteCancellationReason[] | { error: string }
  loading: boolean
}

export function RoutePanel({ origin, destination, onClose }: Props) {
  const panelRef = useRef<HTMLDivElement>(null)
  const closeBtnRef = useRef<HTMLButtonElement>(null)
  const triggerRef = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null)
  const [state, setState] = useState<PanelState>({ daily: [], carriers: [], reasons: [], loading: true })

  useEscape(onClose)
  useClickOutside(panelRef, onClose)

  useEffect(() => {
    closeBtnRef.current?.focus()
    return () => triggerRef.current?.focus()
  }, [])

  useEffect(() => {
    let cancelled = false
    Promise.allSettled([
      queryRouteDaily(origin, destination),
      queryRouteCarriers(origin, destination),
      queryRouteReasons(origin, destination),
    ]).then(([daily, carriers, reasons]) => {
      if (cancelled) return
      setState({
        daily: daily.status === 'fulfilled' ? daily.value : { error: 'Couldn\'t load daily timeliness.' },
        carriers: carriers.status === 'fulfilled' ? carriers.value : { error: 'Couldn\'t load carrier breakdown.' },
        reasons: reasons.status === 'fulfilled' ? reasons.value : { error: 'Couldn\'t load cancellation reasons.' },
        loading: false,
      })
    })
    return () => { cancelled = true }
  }, [origin, destination])

  return (
    <div className="route-panel-backdrop">
      <aside
        ref={panelRef}
        className="route-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="route-panel-heading"
      >
        <header>
          <h3 id="route-panel-heading">{origin} → {destination}</h3>
          <button ref={closeBtnRef} onClick={onClose} aria-label="Close panel">×</button>
        </header>
        <RoutePanelDailySparkline data={state.daily} />
        <RoutePanelCarrierBreakdown data={state.carriers} />
        <RoutePanelReasonMix data={state.reasons} />
      </aside>
    </div>
  )
}
```

- [ ] **Step 3: Implement the three sub-charts**

Each takes `data: T[] | { error: string }`. Renders Highcharts when array, error message when object, empty-state message when array is empty. All lazy-loaded inside `<Suspense>` from RoutePanel.

- [ ] **Step 4: Add CSS**

```css
.route-panel-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  pointer-events: none;
}

.route-panel {
  position: fixed;
  top: 0;
  right: 0;
  height: 100%;
  width: 440px;
  background: var(--color-surface);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.08);
  padding: 1.5rem;
  overflow-y: auto;
  pointer-events: auto;
  transform: translateX(100%);
  animation: panel-slide-in 240ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes panel-slide-in {
  to { transform: translateX(0); }
}

@media (max-width: 768px) {
  .route-panel {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .route-panel {
    animation: none;
    transform: translateX(0);
  }
}
```

- [ ] **Step 5: Wire into FlightLookup**

```tsx
{params.route && (
  <RoutePanel
    origin={params.route.split('-')[0]}
    destination={params.route.split('-')[1]}
    onClose={() => setParams({ route: null })}
  />
)}
```

Click handler on each result card:

```tsx
onClick={() => setParams({ route: `${r.origin_icao}-${r.destination_icao}` })}
```

- [ ] **Step 6: Run tests + bundle check**

```bash
cd frontend && npm run test:unit && npx tsc --noEmit && npx eslint src tests
npm run build
```

Expected: clean. Bundle: 4 new lazy chunks (RoutePanel, 3 sub-charts), all small.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/FlightLookup/RoutePanel.tsx \
        frontend/src/components/FlightLookup/RoutePanel.test.tsx \
        frontend/src/components/FlightLookup/RoutePanel.css \
        frontend/src/components/FlightLookup/RoutePanelDailySparkline.tsx \
        frontend/src/components/FlightLookup/RoutePanelCarrierBreakdown.tsx \
        frontend/src/components/FlightLookup/RoutePanelReasonMix.tsx \
        frontend/src/components/FlightLookup/FlightLookup.tsx
git commit -m "feat(frontend): RoutePanel side-panel + drill-down sub-charts

440px slide-in panel (full-width on <768px), focus trap, Escape +
click-outside + X button to close. Three lazy-loaded sub-charts run
in parallel via Promise.allSettled so one query failure doesn't take
down the others. URL ?route=KJFK-KLAX persists state across refresh."
```

---

## Task 9: E2E + UAT snapshot extension

**Files:**
- Modify: `frontend/tests/e2e/smoke.spec.ts`
- Modify: `frontend/tests/e2e/uat-snapshot.spec.ts`

- [ ] **Step 1: Extend smoke spec**

```ts
test('flight lookup search + drill-down', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('textbox', { name: /flight route/i }).fill('JFK')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.locator('.result-card')).toHaveCount.greaterThan(0)
  // switch tab
  await page.getByRole('tab', { name: 'Carriers' }).click()
  await expect(page.url()).toContain('tab=carriers')
  await page.getByRole('textbox').fill('DAL')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.locator('.result-card')).toHaveCount.greaterThan(0)
  // drill
  await page.locator('.result-card').first().click()
  await expect(page.locator('.route-panel')).toBeVisible()
  await expect(page.url()).toMatch(/route=[A-Z]{4}-[A-Z]{4}/)
  // close via Escape
  await page.keyboard.press('Escape')
  await expect(page.locator('.route-panel')).toHaveCount(0)
  await expect(page.url()).not.toContain('route=')
})
```

- [ ] **Step 2: Extend UAT snapshot**

Add a search + drill flow to `uat-snapshot.spec.ts`. After the existing landing screenshot, type "JFK", click Search, click first result card, await panel, screenshot panel.

- [ ] **Step 3: Run end-to-end manual UAT (per CLAUDE.md mandate)**

```bash
cd /Users/axel/code/travel_pal && just down -v && just up && just init-buckets && just run-pipeline
cd frontend && npm install && npm run build
npx playwright test --reporter=list
TRAVELPAL_UAT_SNAPSHOT=1 npx playwright test uat-snapshot --reporter=list
```

Expected: all pass. Screenshots in `frontend/test-results/` show populated panel with 3 sub-charts.

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/e2e/smoke.spec.ts frontend/tests/e2e/uat-snapshot.spec.ts
git commit -m "test(e2e): cover search → drill flow + URL state for P2.3"
```

---

## Self-review checklist (run after all tasks)

- [ ] `cd pipeline && uv run pytest tests/ -v` — all pass, ≥80% coverage on new code
- [ ] `cd pipeline && uv run ruff check . && uv run ruff format --check . && uvx ty check .` — clean
- [ ] `cd frontend && npm run test:unit` — all pass
- [ ] `cd frontend && npx tsc --noEmit` — clean
- [ ] `cd frontend && npx eslint src tests` — clean
- [ ] `cd frontend && npm run build` — main chunk still under 150 KB gzip
- [ ] `cd frontend && npx playwright test` — all pass
- [ ] `cd frontend && TRAVELPAL_UAT_SNAPSHOT=1 npx playwright test uat-snapshot` — pass; screenshot shows search + drill working
- [ ] Open PR against master, watch CI green, squash-merge, delete branch
