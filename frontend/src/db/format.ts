export const NULL_PLACEHOLDER = '—'

export function pct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return NULL_PLACEHOLDER
  return `${(n * 100).toFixed(1)}%`
}

export function fmt(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return NULL_PLACEHOLDER
  return n.toFixed(1)
}

// Arrow Date32 columns surface as JS numbers (epoch ms or day count depending on the
// duckdb-wasm Arrow build). Anything in the post-2000 epoch-ms range (>1e10) is treated
// as ms; smaller values are treated as days-since-epoch.
export function fmtDate(value: number | string | Date | null | undefined): string {
  if (value == null) return NULL_PLACEHOLDER
  let d: Date
  if (value instanceof Date) {
    d = value
  } else if (typeof value === 'string') {
    d = new Date(value)
  } else if (Number.isFinite(value)) {
    d = value > 1e10 ? new Date(value) : new Date(value * 86_400_000)
  } else {
    return NULL_PLACEHOLDER
  }
  if (Number.isNaN(d.getTime())) return NULL_PLACEHOLDER
  return d.toISOString().slice(0, 10)
}
