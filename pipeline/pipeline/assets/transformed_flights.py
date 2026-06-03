import subprocess
from pathlib import Path

import pyarrow as pa
from dagster import asset, ResourceParam
from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent / "transforms"


@asset
def transformed_flights(
    pipeline_config: ResourceParam[PipelineConfig],
    raw_flights: pa.Table,
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None:
    result = subprocess.run(
        [
            "dbt",
            "run",
            "--project-dir",
            str(DBT_PROJECT_DIR),
            "--profiles-dir",
            str(DBT_PROJECT_DIR),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt run failed:\n{result.stdout}\n{result.stderr}")
