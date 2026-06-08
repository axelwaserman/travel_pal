# Phase 2.2 — Frontend Perf Polish Design

**Date:** 2026-06-08
**Branch:** `phase2/perf-polish`
**Status:** Approved (Pre-Code Gate complete)

## Goal

Reduce initial JS bundle (currently 636 KB / 200 KB gzipped — over the 150 KB landing-page budget in `~/.claude/rules/web/performance.md`) and harden the parquet → frontend contract so pipeline schema drift surfaces visibly instead of silently corrupting renders.

## Architecture

Two independent changes wrapped in one phase branch:

1. **Highcharts code-split.** Replace the static `import Highcharts from 'highcharts'` + `import HighchartsReact from 'highcharts-react-official'` in `CarrierBar.tsx` and `RouteBar.tsx` with a lazy boundary. The chart components become `React.lazy` modules; their parent `CancellationSection.tsx` wraps them in a `Suspense` fallback that renders a generic spinner sized to the chart card.

2. **Zod parquet validation at the queries.ts boundary.** Define a zod schema for each of the four row shapes returned from DuckDB-WASM. Each query function `safeParse`s its result, logs ZodError details for any failed row, drops bad rows, and returns the partial valid set. Existing `interface` declarations are deleted; consumers import `type X = z.infer<typeof XSchema>` instead.

## Components / file changes

### Highcharts code-split

- `frontend/src/components/CancellationSection/CarrierBar.tsx` — convert default import to dynamic; export remains the same so `React.lazy(() => import('./CarrierBar'))` works.
- `frontend/src/components/CancellationSection/RouteBar.tsx` — same.
- `frontend/src/components/CancellationSection/CancellationSection.tsx` — wrap both `<CarrierBar />` / `<RouteBar />` in `<Suspense fallback={<ChartSpinner />}>`.
- `frontend/src/components/CancellationSection/ChartSpinner.tsx` (new, ~30 lines) — pure CSS spinner sized to chart card height (`min-height: 320px`). Centers a small spinning circle, no Highcharts deps. Reused by both bars.
- `frontend/src/components/CancellationSection/CancellationSection.css` — add `.chart-spinner` rules (rotation keyframe, accessible label).

Bundle expectation: Highcharts moves to its own chunk loaded only when the cancellation section is in viewport. Initial bundle target: under 150 KB gzip.

### Zod parquet validation

- `frontend/src/db/schemas.ts` (new) — zod schemas for `RouteTimelinessSchema`, `DailyTimelinessSchema`, `CarrierCancellationSchema`, `RouteCancellationSchema`. Inferred types exported alongside (`export type RouteTimeliness = z.infer<typeof RouteTimelinessSchema>`, etc).
- `frontend/src/db/queries.ts` — replace inline `interface` declarations with re-exports from `schemas.ts`. Each `queryX()` function does:

  ```ts
  const rows = result.toArray().map(r => r.toJSON())
  const parsed = z.array(XSchema).safeParse(rows)
  if (!parsed.success) {
    console.warn('queryX: schema drift detected', parsed.error.issues.slice(0, 5))
    // Filter out invalid rows individually so we still return the valid subset.
    return rows
      .map(r => XSchema.safeParse(r))
      .filter((p): p is { success: true; data: X } => p.success)
      .map(p => p.data)
  }
  return parsed.data
  ```

- `frontend/package.json` — add `zod` dep (already in resolutions if present? check).
- `frontend/src/db/queries.test.ts` (new) — unit tests covering: valid row passes through, invalid row dropped from result, all-invalid returns empty array + logs warning.

### Schema definitions (full bodies)

```ts
// frontend/src/db/schemas.ts
import { z } from 'zod'

export const RouteTimelinessSchema = z.object({
  origin_icao: z.string(),
  destination_icao: z.string(),
  total_flights: z.number(),
  avg_delay_minutes: z.number().nullable(),
  delay_volatility: z.number().nullable(),
  on_time_ratio: z.number().nullable(),
})
export type RouteTimeliness = z.infer<typeof RouteTimelinessSchema>

export const DailyTimelinessSchema = z.object({
  // Arrow Date32 surfaces as number | string | Date depending on duckdb-wasm
  // build; keep loose, fmtDate normalises downstream.
  flight_date: z.union([z.number(), z.string(), z.date()]),
  origin_icao: z.string(),
  total_flights: z.number(),
  avg_delay_minutes: z.number().nullable(),
  delay_volatility: z.number().nullable(),
  on_time_ratio: z.number().nullable(),
})
export type DailyTimeliness = z.infer<typeof DailyTimelinessSchema>

export const CarrierCancellationSchema = z.object({
  origin_icao: z.string(),
  carrier_icao: z.string(),
  carrier_name: z.string(),
  total_scheduled: z.number(),
  cancelled: z.number(),
  cancellation_rate: z.number().nullable(),
  period_start: z.union([z.number(), z.string(), z.date()]),
  period_end: z.union([z.number(), z.string(), z.date()]),
})
export type CarrierCancellation = z.infer<typeof CarrierCancellationSchema>

export const RouteCancellationSchema = z.object({
  origin_icao: z.string(),
  destination_icao: z.string(),
  total_scheduled: z.number(),
  cancelled: z.number(),
  cancellation_rate: z.number().nullable(),
  period_start: z.union([z.number(), z.string(), z.date()]),
  period_end: z.union([z.number(), z.string(), z.date()]),
})
export type RouteCancellation = z.infer<typeof RouteCancellationSchema>
```

## Data flow

Unchanged for runtime path. Validation injected at `queries.ts` boundary only; consumers (`CancellationSection`, etc.) see the same shapes as before.

## Error handling

- **Highcharts dynamic import fails:** `React.lazy` rejects → React boundary catches. Add a small error boundary in `CancellationSection.tsx` that renders "Charts failed to load" with retry button. (Phase 1 already has `<ErrorBoundary>` if not, add a one-file boundary; otherwise swap inline.)
- **Zod parse fails on all rows:** `console.warn` with first 5 issues; `queryX()` returns `[]`; downstream component renders its existing empty state.
- **Zod parse fails on subset:** filter + return valid subset; `console.warn` with count + first 5 issues.

## Testing

- **Unit:** new `queries.test.ts` with three cases per query (all-valid, partial-invalid, all-invalid). Use a fake `getDb()` returning a stub Arrow result.
- **Vitest existing:** update `App.test.tsx` / `CancellationSection.test.tsx` if they construct typed objects directly — the inferred types should be drop-in replacements.
- **E2E:** existing smoke spec asserts 2 SVGs after 15s timeout; bump fallback timeout if dynamic load adds latency. Verify `uat-snapshot.spec.ts` still captures both charts.
- **Bundle measurement:** run `npm run build` before/after and record `dist/assets/index-*.js` gzipped size. Document drop in PR body.

## Out of scope

- React Query / SWR (deferred to P2.3 flight lookup which actually benefits from cache invalidation).
- Code-splitting outside Highcharts (App.tsx tree is small, gains marginal).
- Pipeline-side schema validation (separate concern; dbt schema tests already cover not-null contracts).
