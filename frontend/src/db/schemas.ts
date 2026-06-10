import { z } from 'zod'

// DuckDB-WASM's Arrow toJSON() returns BigInt for INTEGER / BIGINT columns, not
// JS number. z.coerce.number() accepts BigInt, number, and string and coerces
// to a JS number, which is what all downstream consumers expect.
const NUMERIC_FIELD = z.coerce.number()
const NULLABLE_NUMERIC = z.coerce.number().nullable()

// Arrow Date32 surfaces as number | string | Date | BigInt depending on
// duckdb-wasm Arrow build; keep loose, fmtDate normalises downstream.
// Extracted from inline unions in P2.2 quality review (DRY violation fix).
const DATE_FIELD = z.union([z.coerce.number(), z.string(), z.date()])

export const RouteTimelinessSchema = z.object({
  origin_icao: z.string(),
  destination_icao: z.string(),
  total_flights: NUMERIC_FIELD,
  avg_delay_minutes: NULLABLE_NUMERIC,
  delay_volatility: NULLABLE_NUMERIC,
  on_time_ratio: NULLABLE_NUMERIC,
})
export type RouteTimeliness = z.infer<typeof RouteTimelinessSchema>

export const DailyTimelinessSchema = z.object({
  flight_date: DATE_FIELD,
  origin_icao: z.string(),
  total_flights: NUMERIC_FIELD,
  avg_delay_minutes: NULLABLE_NUMERIC,
  delay_volatility: NULLABLE_NUMERIC,
  on_time_ratio: NULLABLE_NUMERIC,
})
export type DailyTimeliness = z.infer<typeof DailyTimelinessSchema>

export const CarrierCancellationSchema = z.object({
  origin_icao: z.string(),
  carrier_icao: z.string(),
  carrier_name: z.string(),
  total_scheduled: NUMERIC_FIELD,
  cancelled: NUMERIC_FIELD,
  cancellation_rate: NULLABLE_NUMERIC,
  period_start: DATE_FIELD,
  period_end: DATE_FIELD,
})
export type CarrierCancellation = z.infer<typeof CarrierCancellationSchema>

export const RouteCancellationSchema = z.object({
  origin_icao: z.string(),
  destination_icao: z.string(),
  total_scheduled: NUMERIC_FIELD,
  cancelled: NUMERIC_FIELD,
  cancellation_rate: NULLABLE_NUMERIC,
  period_start: DATE_FIELD,
  period_end: DATE_FIELD,
})
export type RouteCancellation = z.infer<typeof RouteCancellationSchema>

// ---------------------------------------------------------------------------
// P2.3 — new schemas for search + drill-down
// ---------------------------------------------------------------------------

export const RouteTimelinessWithAirportNameSchema = RouteTimelinessSchema.extend({
  origin_name: z.string(),
  destination_name: z.string(),
})
export type RouteTimelinessWithAirportName = z.infer<typeof RouteTimelinessWithAirportNameSchema>

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
