export const NULL_PLACEHOLDER = '—'

export function pct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return NULL_PLACEHOLDER
  return `${(n * 100).toFixed(1)}%`
}

export function fmt(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return NULL_PLACEHOLDER
  return n.toFixed(1)
}
