import os

import duckdb
import pyarrow as pa
from dagster import AssetIn, Nothing, ResourceParam, asset

from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource

# Maps mart name → source reference.
#   - For S3-backed mart parquets the value equals the mart name; the loop
#     builds the full s3:// URI from it.
#   - For dbt seeds the value is a schema-qualified table reference
#     (e.g. "main_ref.dim_airport"). The dot signals "read from the dbt
#     DuckDB file" instead of an S3 parquet.
_MARTS: tuple[str, ...] = (
    "agg_route_timeliness",
    "agg_daily_timeliness",
    "agg_carrier_cancellations",
    "agg_route_cancellations",
    "agg_carrier_route_cancellations",
    "agg_route_cancellation_reasons",
    "dim_airport",
    "dim_carrier",
)

_MART_SOURCES: dict[str, str] = {
    "agg_route_timeliness": "agg_route_timeliness",
    "agg_daily_timeliness": "agg_daily_timeliness",
    "agg_carrier_cancellations": "agg_carrier_cancellations",
    "agg_route_cancellations": "agg_route_cancellations",
    "agg_carrier_route_cancellations": "agg_carrier_route_cancellations",
    "agg_route_cancellation_reasons": "agg_route_cancellation_reasons",
    # dbt seeds — schema-qualified table names (dot = dbt DuckDB file source)
    "dim_airport": "main_ref.dim_airport",
    "dim_carrier": "main_ref.dim_carrier",
}

_EXPORT_KEYS: dict[str, str] = {
    "agg_route_timeliness": "route_timeliness.parquet",
    "agg_daily_timeliness": "daily_timeliness.parquet",
    "agg_carrier_cancellations": "carrier_cancellations.parquet",
    "agg_route_cancellations": "route_cancellations.parquet",
    "agg_carrier_route_cancellations": "carrier_route_cancellations.parquet",
    "agg_route_cancellation_reasons": "route_cancellation_reasons.parquet",
    # "../" prefix is a sentinel meaning "write to bucket root, not per-airport"
    "dim_airport": "../dim_airport.parquet",
    "dim_carrier": "../dim_carrier.parquet",
}

# Marts are airport-agnostic; export keys namespace by airport, so each file
# must only contain rows that pertain to that airport.
#
# - agg_route_timeliness / agg_route_cancellations have origin + destination,
#   "route through KJFK" can flow either way → filter on either.
# - agg_daily_timeliness groups by (date, origin_icao) only.
# - agg_carrier_cancellations groups by (origin_icao, carrier_icao) only.
# - None → no airport filter; full table exported (used for dim seeds).
_MART_AIRPORT_PREDICATE: dict[str, str | None] = {
    "agg_route_timeliness": "origin_icao = $airport OR destination_icao = $airport",
    "agg_daily_timeliness": "origin_icao = $airport",
    "agg_carrier_cancellations": "origin_icao = $airport",
    "agg_route_cancellations": "origin_icao = $airport OR destination_icao = $airport",
    "agg_carrier_route_cancellations": "origin_icao = $airport OR destination_icao = $airport",
    "agg_route_cancellation_reasons": "origin_icao = $airport OR destination_icao = $airport",
    "dim_airport": None,  # full table, no airport scope
    "dim_carrier": None,  # full table, no airport scope
}

_MART_NAMES = set(_MARTS)
assert _MART_NAMES == set(_MART_SOURCES) == set(_EXPORT_KEYS) == set(_MART_AIRPORT_PREDICATE), (
    "frontend_exports: _MARTS / _MART_SOURCES / _EXPORT_KEYS / _MART_AIRPORT_PREDICATE "
    "must all share the same keys; mismatch indicates a forgotten dict entry"
)

# Sentinel prefix that signals a key should be written at the bucket root
# rather than under {airport_icao}/. Never used literally as an S3 key segment.
_ROOT_KEY_PREFIX = "../"


def _configure_s3(con: duckdb.DuckDBPyConnection, config: PipelineConfig) -> None:
    endpoint = config.seaweedfs_endpoint.removeprefix("http://").removeprefix("https://")
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(f"SET s3_endpoint='{endpoint}'")
    con.execute(f"SET s3_access_key_id='{config.seaweedfs_access_key}'")
    con.execute(f"SET s3_secret_access_key='{config.seaweedfs_secret_key}'")
    con.execute("SET s3_use_ssl=false")
    con.execute("SET s3_url_style='path'")


def _is_dbt_table_source(source: str) -> bool:
    """Return True when the source is a schema-qualified DuckDB table (contains a dot)."""
    return "." in source


def _read_dbt_table(dbt_path: str, table_ref: str) -> pa.Table:
    """Open the dbt DuckDB file and read a table by its schema-qualified name."""
    if table_ref not in _MART_SOURCES.values():
        raise ValueError(f"refusing to read unknown table {table_ref!r}; not in _MART_SOURCES")
    with duckdb.connect(dbt_path) as con:
        return con.execute(f"SELECT * FROM {table_ref}").to_arrow_table()  # noqa: S608


def _resolve_s3_key(airport_icao: str, export_key: str) -> str:
    """Resolve the final S3 object key from the export_key template.

    Keys starting with '../' are written at the bucket root (airport-agnostic).
    All other keys are placed under {airport_icao}/.
    """
    if export_key.startswith(_ROOT_KEY_PREFIX):
        return export_key.removeprefix(_ROOT_KEY_PREFIX)
    return f"{airport_icao}/{export_key}"


@asset(ins={"transformed_flights": AssetIn(dagster_type=Nothing)})
def frontend_exports(
    pipeline_config: ResourceParam[PipelineConfig],
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None:
    dbt_path = os.environ.get("DBT_DUCKDB_PATH", "/tmp/travel_pal.duckdb")
    with duckdb.connect(":memory:") as con:
        _configure_s3(con, pipeline_config)
        for mart in _MARTS:
            source = _MART_SOURCES[mart]
            predicate = _MART_AIRPORT_PREDICATE[mart]
            export_key = _EXPORT_KEYS[mart]

            if _is_dbt_table_source(source):
                # Dim seeds live in the dbt DuckDB file, not S3.
                # predicate is always None for these; no airport filtering.
                arrow_table = _read_dbt_table(dbt_path, source)
            else:
                s3_uri = f"s3://{pipeline_config.raw_bucket}/warehouse/marts/{source}.parquet"
                if predicate is not None:
                    sql = f"SELECT * FROM read_parquet('{s3_uri}') WHERE {predicate}"
                    arrow_table = con.execute(
                        sql, {"airport": pipeline_config.airport_icao}
                    ).to_arrow_table()
                else:
                    sql = f"SELECT * FROM read_parquet('{s3_uri}')"
                    arrow_table = con.execute(sql).to_arrow_table()

            key = _resolve_s3_key(pipeline_config.airport_icao, export_key)
            seaweedfs.upload_parquet(
                arrow_table,
                bucket=pipeline_config.export_bucket,
                key=key,
            )
