import { z } from 'zod'
import { getDb, SEAWEEDFS_PUBLIC_BASE, SEAWEEDFS_PUBLIC_BASE_ROOT } from './client'
import {
  CarrierCancellationSchema,
  CarrierRouteCancellationSchema,
  DailyRouteCancellationSchema,
  DailyTimelinessSchema,
  RouteCancellationReasonSchema,
  RouteCancellationSchema,
  RouteTimelinessSchema,
  RouteTimelinessWithAirportNameSchema,
  type CarrierCancellation,
  type CarrierRouteCancellation,
  type DailyRouteCancellation,
  type DailyTimeliness,
  type RouteCancellation,
  type RouteCancellationReason,
  type RouteTimeliness,
  type RouteTimelinessWithAirportName,
} from './schemas'

export type {
  CarrierCancellation,
  CarrierRouteCancellation,
  DailyRouteCancellation,
  DailyTimeliness,
  RouteCancellation,
  RouteCancellationReason,
  RouteTimeliness,
  RouteTimelinessWithAirportName,
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

// ---------------------------------------------------------------------------
// P2.3 — new query functions for search + drill-down panel
// ---------------------------------------------------------------------------

/**
 * Airport tab search: route_timeliness JOINed to dim_airport so results include
 * human-readable airport names. Accepts ICAO, IATA, or substring of name.
 * Sanitization: strip anything not A-Z, 0-9 (airports have no spaces in codes).
 * LIMIT 200 per spec.
 */
export async function queryAirportSearch(
  airportIcao: string,
  term: string
): Promise<RouteTimelinessWithAirportName[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
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
    try {
      const result = await stmt.query(like)
      const rows = result.toArray().map(r => r.toJSON())
      return parsePartial(RouteTimelinessWithAirportNameSchema, rows, 'queryAirportSearch')
    } finally {
      await stmt.close()
    }
  } finally {
    await conn.close()
  }
}

/**
 * Carrier tab search: agg_carrier_cancellations JOINed to dim_carrier so results
 * can be matched by IATA code, ICAO code, or carrier name substring.
 * Sanitization: allow spaces + hyphens (e.g. "Air France", "Air-France").
 * LIMIT 50 per spec.
 */
export async function queryCarrierSearch(
  airportIcao: string,
  term: string
): Promise<CarrierCancellation[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
    const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/carrier_cancellations.parquet`
    const dimUrl = `${SEAWEEDFS_PUBLIC_BASE_ROOT}/dim_carrier.parquet`
    // Allow spaces + hyphens so "Air France" and "Air-France" both work.
    const sanitized = term.replace(/[^A-Za-z0-9 -]/g, '').toUpperCase()
    const like = `%${sanitized}%`
    const stmt = await conn.prepare(
      `SELECT r.*
       FROM read_parquet('${url}') AS r
       JOIN read_parquet('${dimUrl}') AS c ON c.icao = r.carrier_icao
       WHERE upper(r.carrier_icao) LIKE $1
          OR upper(c.iata) LIKE $1
          OR upper(r.carrier_name) LIKE $1
       ORDER BY r.cancellation_rate DESC
       LIMIT 50`
    )
    try {
      const result = await stmt.query(like)
      const rows = result.toArray().map(r => r.toJSON())
      return parsePartial(CarrierCancellationSchema, rows, 'queryCarrierSearch')
    } finally {
      await stmt.close()
    }
  } finally {
    await conn.close()
  }
}

/**
 * Drill-down: daily on-time ratio for a specific origin → destination route.
 * Reads the per-airport daily_timeliness parquet and filters by both ICAOs.
 */
export async function queryRouteDaily(
  airportIcao: string,
  originIcao: string,
  destinationIcao: string
): Promise<DailyRouteCancellation[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
    // Drill-down parquets live under the configured airport prefix
    // (frontend-exports/{airportIcao}/...); the route's origin can differ
    // from the configured airport (e.g. KCVG → KJFK when airport = KJFK).
    // daily_route_cancellations.parquet is BTS-derived (per date × origin ×
    // destination); the legacy daily_timeliness mart only had origin so it
    // couldn't filter by route.
    const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/daily_route_cancellations.parquet`
    const stmt = await conn.prepare(
      `SELECT * FROM read_parquet('${url}')
       WHERE origin_icao = $1
         AND destination_icao = $2
       ORDER BY flight_date`
    )
    try {
      const result = await stmt.query(originIcao, destinationIcao)
      const rows = result.toArray().map(r => r.toJSON())
      return parsePartial(DailyRouteCancellationSchema, rows, 'queryRouteDaily')
    } finally {
      await stmt.close()
    }
  } finally {
    await conn.close()
  }
}

/**
 * Drill-down: carrier breakdown for a specific origin → destination route.
 * Reads the per-airport carrier_route_cancellations parquet and filters by both ICAOs.
 */
export async function queryRouteCarriers(
  airportIcao: string,
  originIcao: string,
  destinationIcao: string
): Promise<CarrierRouteCancellation[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
    const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/carrier_route_cancellations.parquet`
    const stmt = await conn.prepare(
      `SELECT * FROM read_parquet('${url}')
       WHERE origin_icao = $1
         AND destination_icao = $2
       ORDER BY cancellation_rate DESC`
    )
    try {
      const result = await stmt.query(originIcao, destinationIcao)
      const rows = result.toArray().map(r => r.toJSON())
      return parsePartial(CarrierRouteCancellationSchema, rows, 'queryRouteCarriers')
    } finally {
      await stmt.close()
    }
  } finally {
    await conn.close()
  }
}

/**
 * Drill-down: cancellation reason mix for a specific origin → destination route.
 * Reads the per-airport route_cancellation_reasons parquet and filters by both ICAOs.
 */
export async function queryRouteReasons(
  airportIcao: string,
  originIcao: string,
  destinationIcao: string
): Promise<RouteCancellationReason[]> {
  const db = await getDb()
  const conn = await db.connect()
  try {
    const url = `${SEAWEEDFS_PUBLIC_BASE}/${airportIcao}/route_cancellation_reasons.parquet`
    const stmt = await conn.prepare(
      `SELECT * FROM read_parquet('${url}')
       WHERE origin_icao = $1
         AND destination_icao = $2
       ORDER BY reason_share DESC`
    )
    try {
      const result = await stmt.query(originIcao, destinationIcao)
      const rows = result.toArray().map(r => r.toJSON())
      return parsePartial(RouteCancellationReasonSchema, rows, 'queryRouteReasons')
    } finally {
      await stmt.close()
    }
  } finally {
    await conn.close()
  }
}
