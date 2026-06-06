import { getDb, SEAWEEDFS_PUBLIC_BASE } from './client'

// total_flights is COUNT(*) in the dbt marts and therefore non-null.
// The aggregate columns (avg_delay_minutes, delay_volatility, on_time_ratio) can be null:
// STDDEV over a single-row group is null; NULLIF(...) on a zero denominator is null.
export interface RouteTimeliness {
  origin_icao: string
  destination_icao: string
  total_flights: number
  avg_delay_minutes: number | null
  delay_volatility: number | null
  on_time_ratio: number | null
}

// flight_date arrives from Arrow as either an epoch-ms number, a days-since-epoch
// number, or an ISO string depending on the duckdb-wasm Arrow build — keep it loose
// here and let format.fmtDate normalise.
export interface DailyTimeliness {
  flight_date: number | string | Date
  origin_icao: string
  total_flights: number
  avg_delay_minutes: number | null
  delay_volatility: number | null
  on_time_ratio: number | null
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
    return result.toArray().map((r) => r.toJSON() as RouteTimeliness)
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
      return result.toArray().map((r) => r.toJSON() as RouteTimeliness)
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
    return result.toArray().map((r) => r.toJSON() as DailyTimeliness)
  } finally {
    await conn.close()
  }
}

export interface CarrierCancellation {
  origin_icao: string
  carrier_icao: string
  carrier_name: string
  total_scheduled: number
  cancelled: number
  cancellation_rate: number
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
    return result.toArray().map((r) => r.toJSON() as CarrierCancellation)
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
    return result.toArray().map((r) => r.toJSON() as RouteCancellation)
  } finally {
    await conn.close()
  }
}
