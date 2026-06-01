import subprocess
import pyarrow as pa
from dagster import asset
from pipeline.config import PipelineConfig


@asset
def transformed_flights(
    pipeline_config: PipelineConfig,
    raw_flights: pa.Table,
    seaweedfs,
) -> None:
    result = subprocess.run(
        ["dbt", "run", "--project-dir", "transforms", "--profiles-dir", "transforms"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt run failed:\n{result.stdout}\n{result.stderr}")
