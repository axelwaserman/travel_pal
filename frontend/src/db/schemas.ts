import { z } from 'zod'

// DuckDB-WASM's Arrow toJSON() returns BigInt for INTEGER / BIGINT columns, not
// JS number. z.coerce.number() accepts BigInt, number, and string and coerces
// to a JS number, which is what all downstream consumers expect.
const NUMERIC_FIELD = z.coerce.number()
const NULLABLE_NUMERIC = z.coerce.number().nullable()

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
  // Arrow Date32 surfaces as number | string | Date | BigInt depending on
  // duckdb-wasm Arrow build; keep loose, fmtDate normalises downstream.
  flight_date: z.union([z.coerce.number(), z.string(), z.date()]),
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
  period_start: z.union([z.coerce.number(), z.string(), z.date()]),
  period_end: z.union([z.coerce.number(), z.string(), z.date()]),
})
export type CarrierCancellation = z.infer<typeof CarrierCancellationSchema>

export const RouteCancellationSchema = z.object({
  origin_icao: z.string(),
  destination_icao: z.string(),
  total_scheduled: NUMERIC_FIELD,
  cancelled: NUMERIC_FIELD,
  cancellation_rate: NULLABLE_NUMERIC,
  period_start: z.union([z.coerce.number(), z.string(), z.date()]),
  period_end: z.union([z.coerce.number(), z.string(), z.date()]),
})
export type RouteCancellation = z.infer<typeof RouteCancellationSchema>
