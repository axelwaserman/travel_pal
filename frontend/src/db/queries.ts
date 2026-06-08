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

const MAX_LOGGED_ISSUES = 5

export function parsePartial<T extends z.ZodType<object>>(
  schema: T,
  rows: unknown[],
  label: string
): z.infer<T>[] {
  const parsed = rows.map(r => schema.safeParse(r))
  const invalid = parsed.filter(p => !p.success)
  if (invalid.length > 0) {
    console.warn(
      `[queries:${label}] dropped ${invalid.length}/${rows.length} invalid rows`,
      invalid.slice(0, MAX_LOGGED_ISSUES).map(p => (!p.success ? p.error.issues : []))
    )
  }
  return parsed
    .filter((p): p is { success: true; data: z.infer<T> } => p.success)
    .map(p => p.data)
}

export async function queryRouteTimeliness(
  airportIcao: string
): Promise<RouteTimeliness[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
    // airportIcao comes from internal config (ICAO format: A-Z0-9), not user input — string interpolation is safe
    const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/route_timeliness.parquet`
    const result = await conn.query(
      `SELECT * FROM read_parquet('${url}') ORDER BY total_flights DESC`
    )
    const rows = result.toArray().map(r => r.toJSON())
    return parsePartial(RouteTimelinessSchema, rows, 'queryRouteTimeliness')
  } finally {
    await conn.close()
  }
}

export async function queryFlightLookup(
  airportIcao: string,
  searchTerm: string
): Promise<RouteTimeliness[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
    const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/route_timeliness.parquet`
    // Sanitize searchTerm: ICAO codes are A-Z and 0-9 only (3-4 chars).
    // Strip any character that is not alphanumeric to eliminate injection risk,
    // then wrap in % wildcards for the LIKE predicate.
    const sanitized = searchTerm.replace(/[^A-Za-z0-9]/g, '').toUpperCase()
    const term = `%${sanitized}%`
    const stmt = await conn.prepare(
      `SELECT * FROM read_parquet('${url}')
       WHERE upper(origin_icao) LIKE $1
          OR upper(destination_icao) LIKE $1
       ORDER BY on_time_ratio DESC
       LIMIT 20`
    )
    try {
      const result = await stmt.query(term)
      const rows = result.toArray().map(r => r.toJSON())
      return parsePartial(RouteTimelinessSchema, rows, 'queryFlightLookup')
    } finally {
      await stmt.close()
    }
  } finally {
    await conn.close()
  }
}

export async function queryDailyTimeliness(
  airportIcao: string
): Promise<DailyTimeliness[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
    // airportIcao comes from internal config (ICAO format: A-Z0-9), not user input — string interpolation is safe
    const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/daily_timeliness.parquet`
    const result = await conn.query(
      `SELECT * FROM read_parquet('${url}') ORDER BY flight_date`
    )
    const rows = result.toArray().map(r => r.toJSON())
    return parsePartial(DailyTimelinessSchema, rows, 'queryDailyTimeliness')
  } finally {
    await conn.close()
  }
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
    const rows = result.toArray().map(r => r.toJSON())
    return parsePartial(CarrierCancellationSchema, rows, 'queryCarrierCancellations')
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
    const rows = result.toArray().map(r => r.toJSON())
    return parsePartial(RouteCancellationSchema, rows, 'queryRouteCancellations')
  } finally {
    await conn.close()
  }
}
