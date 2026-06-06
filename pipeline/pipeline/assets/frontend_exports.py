import duckdb
import pyarrow as pa
from dagster import AssetIn, Nothing, ResourceParam, asset

from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource

_MARTS = (
    "agg_route_timeliness",
    "agg_daily_timeliness",
    "agg_carrier_cancellations",
    "agg_route_cancellations",
)
_EXPORT_KEYS = {
    "agg_route_timeliness": "route_timeliness.parquet",
    "agg_daily_timeliness": "daily_timeliness.parquet",
    "agg_carrier_cancellations": "carrier_cancellations.parquet",
    "agg_route_cancellations": "route_cancellations.parquet",
}
# Marts are airport-agnostic; export keys namespace by airport, so each file
# must only contain rows that pertain to that airport.
#
# - agg_route_timeliness / agg_route_cancellations have origin + destination,
#   "route through KJFK" can flow either way → filter on either.
# - agg_daily_timeliness groups by (date, origin_icao) only.
# - agg_carrier_cancellations groups by (origin_icao, carrier_icao) only.
_MART_AIRPORT_PREDICATE = {
    "agg_route_timeliness": "origin_icao = $airport OR destination_icao = $airport",
    "agg_daily_timeliness": "origin_icao = $airport",
    "agg_carrier_cancellations": "origin_icao = $airport",
    "agg_route_cancellations": "origin_icao = $airport OR destination_icao = $airport",
}


def _configure_s3(con: duckdb.DuckDBPyConnection, config: PipelineConfig) -> None:
    endpoint = config.seaweedfs_endpoint.removeprefix("http://").removeprefix("https://")
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(f"SET s3_endpoint='{endpoint}'")
    con.execute(f"SET s3_access_key_id='{config.seaweedfs_access_key}'")
    con.execute(f"SET s3_secret_access_key='{config.seaweedfs_secret_key}'")
    con.execute("SET s3_use_ssl=false")
    con.execute("SET s3_url_style='path'")


@asset(ins={"transformed_flights": AssetIn(dagster_type=Nothing)})
def frontend_exports(
    pipeline_config: ResourceParam[PipelineConfig],
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None:
    with duckdb.connect(":memory:") as con:
        _configure_s3(con, pipeline_config)
        for mart in _MARTS:
            source = f"s3://{pipeline_config.raw_bucket}/warehouse/marts/{mart}.parquet"
            predicate = _MART_AIRPORT_PREDICATE[mart]
            sql = f"SELECT * FROM read_parquet('{source}') WHERE {predicate}"
            arrow_table: pa.Table = con.execute(
                sql, {"airport": pipeline_config.airport_icao}
            ).to_arrow_table()
            seaweedfs.upload_parquet(
                arrow_table,
                bucket=pipeline_config.export_bucket,
                key=f"{pipeline_config.airport_icao}/{_EXPORT_KEYS[mart]}",
            )
