import * as duckdb from '@duckdb/duckdb-wasm'

let db: duckdb.AsyncDuckDB | null = null

const SEAWEEDFS_PUBLIC_BASE =
  import.meta.env.VITE_SEAWEEDFS_PUBLIC_BASE ?? 'http://localhost:8333/frontend-exports'

export async function getDb(): Promise<duckdb.AsyncDuckDB> {
  if (db) return db

  const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles()
  const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES)
  const worker_url = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker!}");`], { type: 'text/javascript' })
  )
  const worker = new Worker(worker_url)
  const logger = new duckdb.ConsoleLogger()
  db = new duckdb.AsyncDuckDB(logger, worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)

  const conn = await db.connect()
  await conn.query('INSTALL httpfs; LOAD httpfs;')
  await conn.close()

  return db
}

export { SEAWEEDFS_PUBLIC_BASE }
