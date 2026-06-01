import os
import duckdb
import pyarrow as pa
from dagster import asset, AssetIn, Nothing
from pipeline.config import PipelineConfig


@asset(ins={"transformed_flights": AssetIn(dagster_type=Nothing)})
def frontend_exports(
    pipeline_config: PipelineConfig,
    seaweedfs,
) -> None:
    db_path = os.environ.get("DBT_DUCKDB_PATH", "/tmp/travel_pal.duckdb")
    con = duckdb.connect(db_path, read_only=True)

    agg_route = con.execute("SELECT * FROM agg_route_timeliness").arrow()
    seaweedfs.upload_parquet(
        agg_route,
        bucket=pipeline_config.export_bucket,
        key=f"{pipeline_config.airport_icao}/route_timeliness.parquet",
    )

    agg_daily = con.execute("SELECT * FROM agg_daily_timeliness").arrow()
    seaweedfs.upload_parquet(
        agg_daily,
        bucket=pipeline_config.export_bucket,
        key=f"{pipeline_config.airport_icao}/daily_timeliness.parquet",
    )
