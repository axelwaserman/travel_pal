import subprocess
from pathlib import Path

import pyarrow as pa
from dagster import AssetIn, Nothing, ResourceParam, asset

from pipeline.config import PipelineConfig
from pipeline.resources.seaweedfs import SeaweedFSResource

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent / "transforms"


def _run_dbt(subcommand: str) -> None:
    result = subprocess.run(
        [
            "dbt",
            subcommand,
            "--project-dir",
            str(DBT_PROJECT_DIR),
            "--profiles-dir",
            str(DBT_PROJECT_DIR),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt {subcommand} failed:\n{result.stdout}\n{result.stderr}")


@asset(ins={"bts_on_time": AssetIn(dagster_type=Nothing)})
def transformed_flights(
    pipeline_config: ResourceParam[PipelineConfig],
    raw_flights: pa.Table,
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None:
    _run_dbt("seed")
    _run_dbt("run")
