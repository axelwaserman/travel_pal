import duckdb
import pyarrow as pa
from dagster import asset, AssetIn, Nothing, ResourceParam
from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource


_MARTS = ("agg_route_timeliness", "agg_daily_timeliness")
_EXPORT_KEYS = {
    "agg_route_timeliness": "route_timeliness.parquet",
    "agg_daily_timeliness": "daily_timeliness.parquet",
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
            arrow_table: pa.Table = con.execute(
                f"SELECT * FROM read_parquet('{source}')"
            ).to_arrow_table()
            seaweedfs.upload_parquet(
                arrow_table,
                bucket=pipeline_config.export_bucket,
                key=f"{pipeline_config.airport_icao}/{_EXPORT_KEYS[mart]}",
            )
