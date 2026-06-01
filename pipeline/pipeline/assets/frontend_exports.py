import os
import pathlib
import duckdb
import pyarrow as pa
from dagster import asset, AssetIn, Nothing, ResourceParam
from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource


@asset(ins={"transformed_flights": AssetIn(dagster_type=Nothing)})
def frontend_exports(
    pipeline_config: ResourceParam[PipelineConfig],
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None:
    db_path = os.environ.get("DBT_DUCKDB_PATH", "/tmp/travel_pal.duckdb")
    if not pathlib.Path(db_path).exists():
        raise FileNotFoundError(
            f"DuckDB file not found at {db_path!r}. "
            "Ensure transformed_flights completed successfully."
        )

    with duckdb.connect(db_path, read_only=True) as con:
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
