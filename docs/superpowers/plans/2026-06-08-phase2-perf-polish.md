# Phase 2.2 — Frontend Perf Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Each task runs in its own isolated git worktree off `phase2/perf-polish`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut initial bundle below 150 KB gzipped via Highcharts code-split, and harden parquet → frontend contract via zod validation at the queries.ts boundary.

**Architecture:** Two independent changes on one phase branch (PR'd together). Highcharts moves to lazy-loaded chunk; existing TS interfaces in `queries.ts` are replaced by zod-inferred types with runtime validation.

**Tech Stack:** React 18, TypeScript, vite, Highcharts 11, highcharts-react-official, zod (new dep), vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-06-08-phase2-perf-polish-design.md`

---

## Task 1: Highcharts code-split with Suspense + spinner fallback

**Files:**
- Modify: `frontend/src/components/CancellationSection/CancellationSection.tsx`
- Modify: `frontend/src/components/CancellationSection/CarrierBar.tsx`
- Modify: `frontend/src/components/CancellationSection/RouteBar.tsx`
- Modify: `frontend/src/components/CancellationSection/CancellationSection.css`
- Create: `frontend/src/components/CancellationSection/ChartSpinner.tsx`
- Modify: `frontend/src/components/CancellationSection/CancellationSection.test.tsx` (if asserting chart rendering — bump timeout for lazy)

- [ ] **Step 1: Verify current bundle size baseline**

```bash
cd frontend && npm run build 2>&1 | grep "index-"
```

Expected: a single `dist/assets/index-*.js` ~636 KB / ~200 KB gzipped. Record the exact gzipped figure for the PR description.

- [ ] **Step 2: Write the failing E2E timeout test**

Open `frontend/tests/e2e/smoke.spec.ts`. The cancellation chart assertion already has a 15 s timeout — confirm it still passes after the code-split lands. No new test needed; this step just establishes the baseline expectation.

```bash
cd frontend && npx playwright test smoke --reporter=list
```

Expected: 2/2 pass.

- [ ] **Step 3: Create `ChartSpinner.tsx`**

```tsx
// frontend/src/components/CancellationSection/ChartSpinner.tsx
export function ChartSpinner() {
  return (
    <div
      role="status"
      aria-label="Loading chart"
      className="chart-spinner"
    >
      <span className="chart-spinner__circle" />
    </div>
  )
}
```

- [ ] **Step 4: Add spinner CSS**

Append to `frontend/src/components/CancellationSection/CancellationSection.css`:

```css
.chart-spinner {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-spinner__circle {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border, #e5e5e5);
  border-top-color: var(--color-text, #18181b);
  border-radius: 50%;
  animation: chart-spinner-rotate 800ms linear infinite;
}

@keyframes chart-spinner-rotate {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .chart-spinner__circle {
    animation: none;
  }
}
```

- [ ] **Step 5: Lazy-load `CarrierBar` and `RouteBar` from `CancellationSection.tsx`**

Replace the static imports with `lazy` + `Suspense`:

```tsx
// frontend/src/components/CancellationSection/CancellationSection.tsx
import { lazy, Suspense } from 'react'
import { ChartSpinner } from './ChartSpinner'

const CarrierBar = lazy(() =>
  import('./CarrierBar').then(m => ({ default: m.CarrierBar }))
)
const RouteBar = lazy(() =>
  import('./RouteBar').then(m => ({ default: m.RouteBar }))
)

// inside render, wrap each chart usage:
<Suspense fallback={<ChartSpinner />}>
  <CarrierBar data={carriers} airportIcao={airportIcao} />
</Suspense>
<Suspense fallback={<ChartSpinner />}>
  <RouteBar data={routes} airportIcao={airportIcao} />
</Suspense>
```

Both `CarrierBar` and `RouteBar` already export named, not default — `lazy()` requires a default-shaped resolution, hence the `.then(m => ({ default: m.X }))` adapter.

- [ ] **Step 6: Run vitest unit tests**

```bash
cd frontend && npm run test
```

Expected: all pass. If `CancellationSection.test.tsx` now needs `act()` wrapping for the lazy boundary, fix it.

- [ ] **Step 7: Rebuild and measure new bundle**

```bash
cd frontend && npm run build 2>&1 | grep -E "index-|highcharts|chunk"
```

Expected: a separate Highcharts chunk (~400-500 KB raw, ~150 KB gzip), and the main `index-*.js` should drop to under 150 KB gzip. Record both figures.

- [ ] **Step 8: Run Playwright smoke**

```bash
cd frontend && npx playwright test smoke --reporter=list
```

Expected: 2/2 pass.

- [ ] **Step 9: Run gated UAT snapshot**

```bash
cd frontend && TRAVELPAL_UAT_SNAPSHOT=1 npx playwright test uat-snapshot --reporter=list
```

Expected: pass; full-page screenshot in `frontend/test-results/uat-fullpage.png` shows both charts rendered (after the lazy load resolves).

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/CancellationSection/ChartSpinner.tsx \
        frontend/src/components/CancellationSection/CancellationSection.tsx \
        frontend/src/components/CancellationSection/CancellationSection.css
git commit -m "perf(frontend): lazy-load Highcharts via React.lazy + Suspense

Splits Highcharts + highcharts-react-official into a separate chunk
loaded only when the cancellation section renders. Fallback is a small
CSS spinner sized to the chart card so layout stays stable.

Bundle measurement (gzipped):
- Before: <fill in from Step 1>
- After main: <fill in from Step 7>
- After Highcharts chunk: <fill in from Step 7>"
```

---

## Task 2: Zod parquet validation at queries.ts boundary

**Files:**
- Create: `frontend/src/db/schemas.ts`
- Modify: `frontend/src/db/queries.ts` (delete inline interfaces, add safeParse pattern)
- Create: `frontend/src/db/queries.test.ts`
- Modify: `frontend/package.json` (add `zod` dep)
- Modify: `frontend/package-lock.json` (regenerated)

- [ ] **Step 1: Add zod dep**

```bash
cd frontend && npm install zod
```

Pin to a specific minor version (^3.x). Verify it lands in `dependencies`, not `devDependencies`.

- [ ] **Step 2: Create `schemas.ts`**

Full body lifted from the spec section "Schema definitions":

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

- [ ] **Step 3: Write the failing test for `parsePartial` helper**

Create `frontend/src/db/queries.test.ts` first; it will reference a helper `parsePartial` that doesn't exist yet:

```ts
// frontend/src/db/queries.test.ts
import { describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { parsePartial } from './queries'

const Schema = z.object({ id: z.number(), name: z.string() })

describe('parsePartial', () => {
  it('returns parsed rows when all valid', () => {
    const rows = [
      { id: 1, name: 'a' },
      { id: 2, name: 'b' },
    ]
    expect(parsePartial(Schema, rows, 'test')).toEqual(rows)
  })

  it('drops invalid rows and logs a warning', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const rows = [
      { id: 1, name: 'a' },
      { id: 'bad', name: 'b' }, // invalid
      { id: 3, name: 'c' },
    ]
    const result = parsePartial(Schema, rows, 'test')
    expect(result).toEqual([
      { id: 1, name: 'a' },
      { id: 3, name: 'c' },
    ])
    expect(warn).toHaveBeenCalledOnce()
    warn.mockRestore()
  })

  it('returns empty array when all rows invalid', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const rows = [{ id: 'x' }, { id: 'y' }]
    expect(parsePartial(Schema, rows, 'test')).toEqual([])
    expect(warn).toHaveBeenCalledOnce()
    warn.mockRestore()
  })
})
```

```bash
cd frontend && npm run test queries.test
```

Expected: FAIL with "parsePartial is not exported" (or similar).

- [ ] **Step 4: Implement `parsePartial` and integrate in `queries.ts`**

Refactor `queries.ts`. Top of file:

```ts
import { z } from 'zod'
import { getDb, SEAWEEDFS_PUBLIC_BASE } from './client'
import {
  CarrierCancellationSchema,
  DailyTimelinessSchema,
  RouteCancellationSchema,
  RouteTimelinessSchema,
  type CarrierCancellation,
  type DailyTimeliness,
  type RouteCancellation,
  type RouteTimeliness,
} from './schemas'

export type {
  CarrierCancellation,
  DailyTimeliness,
  RouteCancellation,
  RouteTimeliness,
}

export function parsePartial<T extends z.ZodTypeAny>(
  schema: T,
  rows: unknown[],
  label: string
): z.infer<T>[] {
  const parsed = rows.map(r => schema.safeParse(r))
  const invalid = parsed.filter(p => !p.success)
  if (invalid.length > 0) {
    console.warn(
      `[queries:${label}] dropped ${invalid.length}/${rows.length} invalid rows`,
      invalid.slice(0, 5).map(p => (p as { error: z.ZodError }).error.issues)
    )
  }
  return parsed
    .filter((p): p is z.SafeParseSuccess<z.infer<T>> => p.success)
    .map(p => p.data)
}
```

Update each `queryX` function to call `parsePartial` instead of `as TypeName`:

```ts
// example for queryRouteTimeliness
const rows = result.toArray().map(r => r.toJSON())
return parsePartial(RouteTimelinessSchema, rows, 'queryRouteTimeliness')
```

Repeat for `queryFlightLookup`, `queryDailyTimeliness`, `queryCarrierCancellations`, `queryRouteCancellations`. Delete the four `interface` declarations.

- [ ] **Step 5: Run vitest**

```bash
cd frontend && npm run test
```

Expected: all pass including the three new `parsePartial` tests.

- [ ] **Step 6: Run tsc**

```bash
cd frontend && npx tsc --noEmit
```

Expected: clean. If any consumer imports the old `interface`, the type alias re-exported from `queries.ts` keeps them working — but verify.

- [ ] **Step 7: Run Playwright smoke + UAT snapshot**

```bash
cd frontend && npx playwright test --reporter=list
TRAVELPAL_UAT_SNAPSHOT=1 npx playwright test uat-snapshot --reporter=list
```

Expected: all pass. Console errors should be 0 (real parquets match the schemas).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/db/schemas.ts \
        frontend/src/db/queries.ts \
        frontend/src/db/queries.test.ts \
        frontend/package.json \
        frontend/package-lock.json
git commit -m "feat(frontend): zod-validate parquet rows at queries.ts boundary

Replaces hand-written interfaces with z.infer types and runtime
safeParse at every query function. parsePartial drops invalid rows,
logs the first 5 issues to console.warn, and returns the valid subset
so a partial schema drift no longer wedges the UI.

Schemas: RouteTimeliness, DailyTimeliness, CarrierCancellation,
RouteCancellation. Existing consumers untouched (types re-exported
from queries.ts)."
```

---

## Self-review checklist (run after both tasks)

- [ ] `cd frontend && npm run build` succeeds, main chunk under 150 KB gzip
- [ ] `cd frontend && npm run test` 100% pass
- [ ] `cd frontend && npx tsc --noEmit` clean
- [ ] `cd frontend && npx eslint src tests` clean
- [ ] `cd frontend && npx playwright test --reporter=list` 2/2 pass
- [ ] `cd frontend && TRAVELPAL_UAT_SNAPSHOT=1 npx playwright test uat-snapshot --reporter=list` pass
- [ ] No `console.error` in browser during UAT
- [ ] Open PR against master, watch CI green, merge
