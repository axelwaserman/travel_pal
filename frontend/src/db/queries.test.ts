import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { z } from 'zod'
import { parsePartial } from './queries'

// ---------------------------------------------------------------------------
// parsePartial — existing tests
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Helpers for new query function tests
// ---------------------------------------------------------------------------

/** Build a fake Arrow row that has a .toJSON() method returning the given object. */
function fakeRow(data: Record<string, unknown>) {
  return { toJSON: () => data }
}

/** Build a minimal fake DuckDB connection stub. */
function makeConn(rows: ReturnType<typeof fakeRow>[]) {
  const stmt = {
    query: vi.fn().mockResolvedValue({ toArray: () => rows }),
    close: vi.fn().mockResolvedValue(undefined),
  }
  return {
    query: vi.fn().mockResolvedValue({ toArray: () => rows }),
    prepare: vi.fn().mockResolvedValue(stmt),
    close: vi.fn().mockResolvedValue(undefined),
    _stmt: stmt,
  }
}

/** Build a minimal fake DuckDB instance. */
function makeDb(rows: ReturnType<typeof fakeRow>[]) {
  const conn = makeConn(rows)
  return { db: { connect: vi.fn().mockResolvedValue(conn) }, conn }
}

// ---------------------------------------------------------------------------
// queryAirportSearch
// ---------------------------------------------------------------------------

describe('queryAirportSearch', () => {
  beforeEach(() => {
    vi.resetModules()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns RouteTimelinessWithAirportName rows from the stub connection', async () => {
    const row = {
      origin_icao: 'KJFK',
      destination_icao: 'KLAX',
      total_flights: 100,
      avg_delay_minutes: 5.2,
      delay_volatility: 1.1,
      on_time_ratio: 0.82,
      origin_name: 'John F. Kennedy',
      destination_name: 'Los Angeles Intl',
    }
    const { db } = makeDb([fakeRow(row)])
    vi.doMock('./client', () => ({
      getDb: vi.fn().mockResolvedValue(db),
      SEAWEEDFS_PUBLIC_BASE: 'http://mock/fe',
      SEAWEEDFS_PUBLIC_BASE_ROOT: 'http://mock',
    }))
    const { queryAirportSearch } = await import('./queries')
    const result = await queryAirportSearch('KJFK', 'JFK')
    expect(result).toHaveLength(1)
    expect(result[0].origin_icao).toBe('KJFK')
    expect(result[0].origin_name).toBe('John F. Kennedy')
  })

  it('sanitizes the search term — strips non-alphanumeric characters', async () => {
    const row = {
      origin_icao: 'KJFK',
      destination_icao: 'KLAX',
      total_flights: 10,
      avg_delay_minutes: null,
      delay_volatility: null,
      on_time_ratio: null,
      origin_name: 'JFK',
      destination_name: 'LAX',
    }
    const { db, conn } = makeDb([fakeRow(row)])
    vi.doMock('./client', () => ({
      getDb: vi.fn().mockResolvedValue(db),
      SEAWEEDFS_PUBLIC_BASE: 'http://mock/fe',
      SEAWEEDFS_PUBLIC_BASE_ROOT: 'http://mock',
    }))
    const { queryAirportSearch } = await import('./queries')
    await queryAirportSearch('KJFK', "JFK'; DROP TABLE--")
    // prepare should have been called once with a parameterised SQL
    expect(conn.prepare).toHaveBeenCalledOnce()
    // The prepared statement's query() is called with the sanitized term
    const callArg = conn._stmt.query.mock.calls[0][0] as string
    // Should be "%JFKDROPTABLE%" — SQL injection chars stripped
    expect(callArg).not.toContain("'")
    expect(callArg).not.toContain(';')
  })

  it('returns empty array and drops rows that fail schema validation', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    // Missing origin_name — will fail RouteTimelinessWithAirportNameSchema
    const row = { origin_icao: 'KJFK', destination_icao: 'KLAX', total_flights: 10 }
    const { db } = makeDb([fakeRow(row)])
    vi.doMock('./client', () => ({
      getDb: vi.fn().mockResolvedValue(db),
      SEAWEEDFS_PUBLIC_BASE: 'http://mock/fe',
      SEAWEEDFS_PUBLIC_BASE_ROOT: 'http://mock',
    }))
    const { queryAirportSearch } = await import('./queries')
    const result = await queryAirportSearch('KJFK', 'JFK')
    expect(result).toHaveLength(0)
    expect(warn).toHaveBeenCalledOnce()
    warn.mockRestore()
  })
})

// ---------------------------------------------------------------------------
// queryCarrierSearch
// ---------------------------------------------------------------------------

describe('queryCarrierSearch', () => {
  beforeEach(() => {
    vi.resetModules()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns CarrierCancellation rows from the stub connection', async () => {
    const row = {
      origin_icao: 'KJFK',
      carrier_icao: 'DAL',
      carrier_name: 'Delta Air Lines',
      total_scheduled: 500,
      cancelled: 10,
      cancellation_rate: 0.02,
      period_start: '2024-01-01',
      period_end: '2024-12-31',
    }
    const { db } = makeDb([fakeRow(row)])
    vi.doMock('./client', () => ({
      getDb: vi.fn().mockResolvedValue(db),
      SEAWEEDFS_PUBLIC_BASE: 'http://mock/fe',
      SEAWEEDFS_PUBLIC_BASE_ROOT: 'http://mock',
    }))
    const { queryCarrierSearch } = await import('./queries')
    const result = await queryCarrierSearch('KJFK', 'Delta')
    expect(result).toHaveLength(1)
    expect(result[0].carrier_name).toBe('Delta Air Lines')
  })

  it('allows spaces and hyphens in the carrier search term', async () => {
    const row = {
      origin_icao: 'KJFK',
      carrier_icao: 'AFR',
      carrier_name: 'Air France',
      total_scheduled: 200,
      cancelled: 4,
      cancellation_rate: 0.02,
      period_start: '2024-01-01',
      period_end: '2024-12-31',
    }
    const { db, conn } = makeDb([fakeRow(row)])
    vi.doMock('./client', () => ({
      getDb: vi.fn().mockResolvedValue(db),
      SEAWEEDFS_PUBLIC_BASE: 'http://mock/fe',
      SEAWEEDFS_PUBLIC_BASE_ROOT: 'http://mock',
    }))
    const { queryCarrierSearch } = await import('./queries')
    await queryCarrierSearch('KJFK', 'Air France')
    const callArg = conn._stmt.query.mock.calls[0][0] as string
    // Spaces + hyphens allowed; "Air France" should survive sanitization
    expect(callArg).toContain('AIR FRANCE')
  })
})

// ---------------------------------------------------------------------------
// queryRouteDaily
// ---------------------------------------------------------------------------

describe('queryRouteDaily', () => {
  beforeEach(() => {
    vi.resetModules()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns DailyRouteCancellation rows filtered by origin + destination', async () => {
    const row = {
      flight_date: '2024-01-15',
      origin_icao: 'KJFK',
      destination_icao: 'KLAX',
      total_scheduled: 8,
      cancelled: 1,
      cancellation_rate: 0.125,
    }
    const { db } = makeDb([fakeRow(row)])
    vi.doMock('./client', () => ({
      getDb: vi.fn().mockResolvedValue(db),
      SEAWEEDFS_PUBLIC_BASE: 'http://mock/fe',
      SEAWEEDFS_PUBLIC_BASE_ROOT: 'http://mock',
    }))
    const { queryRouteDaily } = await import('./queries')
    const result = await queryRouteDaily('KJFK', 'KJFK', 'KLAX')
    expect(result).toHaveLength(1)
    expect(result[0].origin_icao).toBe('KJFK')
  })
})

// ---------------------------------------------------------------------------
// queryRouteCarriers
// ---------------------------------------------------------------------------

describe('queryRouteCarriers', () => {
  beforeEach(() => {
    vi.resetModules()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns CarrierRouteCancellation rows for origin + destination', async () => {
    const row = {
      origin_icao: 'KJFK',
      destination_icao: 'KLAX',
      carrier_icao: 'DAL',
      carrier_name: 'Delta Air Lines',
      total_scheduled: 120,
      cancelled: 3,
      cancellation_rate: 0.025,
      period_start: '2024-01-01',
      period_end: '2024-12-31',
    }
    const { db } = makeDb([fakeRow(row)])
    vi.doMock('./client', () => ({
      getDb: vi.fn().mockResolvedValue(db),
      SEAWEEDFS_PUBLIC_BASE: 'http://mock/fe',
      SEAWEEDFS_PUBLIC_BASE_ROOT: 'http://mock',
    }))
    const { queryRouteCarriers } = await import('./queries')
    const result = await queryRouteCarriers('KJFK', 'KJFK', 'KLAX')
    expect(result).toHaveLength(1)
    expect(result[0].carrier_icao).toBe('DAL')
  })
})

// ---------------------------------------------------------------------------
// queryRouteReasons
// ---------------------------------------------------------------------------

describe('queryRouteReasons', () => {
  beforeEach(() => {
    vi.resetModules()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns RouteCancellationReason rows for origin + destination', async () => {
    const row = {
      origin_icao: 'KJFK',
      destination_icao: 'KLAX',
      reason: 'Weather',
      cancelled_count: 5,
      reason_share: 0.5,
    }
    const { db } = makeDb([fakeRow(row)])
    vi.doMock('./client', () => ({
      getDb: vi.fn().mockResolvedValue(db),
      SEAWEEDFS_PUBLIC_BASE: 'http://mock/fe',
      SEAWEEDFS_PUBLIC_BASE_ROOT: 'http://mock',
    }))
    const { queryRouteReasons } = await import('./queries')
    const result = await queryRouteReasons('KJFK', 'KJFK', 'KLAX')
    expect(result).toHaveLength(1)
    expect(result[0].reason).toBe('Weather')
  })

  it('drops rows with invalid reason enum values', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const row = {
      origin_icao: 'KJFK',
      destination_icao: 'KLAX',
      reason: 'INVALID_REASON', // not in the enum
      cancelled_count: 5,
      reason_share: 1.0,
    }
    const { db } = makeDb([fakeRow(row)])
    vi.doMock('./client', () => ({
      getDb: vi.fn().mockResolvedValue(db),
      SEAWEEDFS_PUBLIC_BASE: 'http://mock/fe',
      SEAWEEDFS_PUBLIC_BASE_ROOT: 'http://mock',
    }))
    const { queryRouteReasons } = await import('./queries')
    const result = await queryRouteReasons('KJFK', 'KJFK', 'KLAX')
    expect(result).toHaveLength(0)
    expect(warn).toHaveBeenCalledOnce()
    warn.mockRestore()
  })
})
