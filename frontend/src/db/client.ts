import * as duckdb from '@duckdb/duckdb-wasm'

// Memoise the *promise*, not the resolved value, so concurrent callers all
// await the same instantiation. Without this, two queries firing in parallel
// (e.g., Promise.all in CancellationSection) each ran `db.instantiate(...)`
// and stomped on the partially-initialised worker, surfacing as
// "Failed to load" in the UI.
let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null

const SEAWEEDFS_PUBLIC_BASE =
  import.meta.env.VITE_SEAWEEDFS_PUBLIC_BASE ?? 'http://localhost:8333/frontend-exports'

async function instantiate(): Promise<duckdb.AsyncDuckDB> {
  const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles()
  const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES)
  const worker_url = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker!}");`], { type: 'text/javascript' })
  )
  const worker = new Worker(worker_url)
  const logger = new duckdb.ConsoleLogger()
  const db = new duckdb.AsyncDuckDB(logger, worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)

  const conn = await db.connect()
  await conn.query('INSTALL httpfs; LOAD httpfs;')
  await conn.close()

  return db
}

export function getDb(): Promise<duckdb.AsyncDuckDB> {
  if (!dbPromise) {
    dbPromise = instantiate().catch(err => {
      // Reset on failure so a retry can re-instantiate.
      dbPromise = null
      throw err
    })
  }
  return dbPromise
}

export { SEAWEEDFS_PUBLIC_BASE }
