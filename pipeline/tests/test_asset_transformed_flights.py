import pytest
import pyarrow as pa
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from pipeline.assets.transformed_flights import transformed_flights
from pipeline.assets.frontend_exports import frontend_exports
from pipeline.config import PipelineConfig


def _make_config() -> PipelineConfig:
    return PipelineConfig.model_validate({
        "airport_icao": "KJFK",
        "ingest_start_date": "2024-01-01",
        "ingest_end_date": "2024-01-08",
        "SEAWEEDFS_ENDPOINT": "http://localhost:8333",
        "seaweedfs_access_key": "admin",
        "seaweedfs_secret_key": "admin",
        "nessie_endpoint": "http://localhost:19120/api/v1",
    })


CONFIG = _make_config()

AGG_ROUTE_TABLE = pa.table(
    {
        "origin_icao": ["KJFK"],
        "destination_icao": ["KLAX"],
        "total_flights": [100],
        "avg_delay_minutes": [5.2],
        "delay_volatility": [12.1],
        "on_time_ratio": [0.82],
    }
)

AGG_DAILY_TABLE = pa.table(
    {
        "flight_date": pa.array([date(2024, 1, 1)], type=pa.date32()),
        "origin_icao": ["KJFK"],
        "total_flights": [100],
        "avg_delay_minutes": [5.2],
        "delay_volatility": [12.1],
        "on_time_ratio": [0.82],
    }
)


def test_transformed_flights_runs_dbt():
    mock_seaweedfs = MagicMock()
    with patch("pipeline.assets.transformed_flights.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        transformed_flights(
            pipeline_config=CONFIG,
            raw_flights=pa.table({"icao24": ["x"]}),
            seaweedfs=mock_seaweedfs,
        )
    mock_run.assert_called_once()
    cmd = mock_run.call_args.args[0]
    assert "dbt" in cmd
    assert "--project-dir" in cmd
    project_dir_idx = cmd.index("--project-dir") + 1
    assert cmd[project_dir_idx].endswith("/transforms")
    assert Path(cmd[project_dir_idx]).is_absolute()
    # no cwd kwarg — path is absolute so cwd is not needed
    assert "cwd" not in (mock_run.call_args.kwargs or {})


def test_transformed_flights_raises_on_dbt_failure():
    mock_seaweedfs = MagicMock()
    with patch("pipeline.assets.transformed_flights.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="dbt error")
        with pytest.raises(RuntimeError, match="dbt run failed"):
            transformed_flights(
                pipeline_config=CONFIG,
                raw_flights=pa.table({"icao24": ["x"]}),
                seaweedfs=mock_seaweedfs,
            )


def test_frontend_exports_uploads_both_parquet_files():
    mock_seaweedfs = MagicMock()
    mock_con = MagicMock()
    mock_con.__enter__ = lambda s: mock_con
    mock_con.__exit__ = MagicMock(return_value=False)
    mock_con.execute.side_effect = [
        MagicMock(arrow=lambda: AGG_ROUTE_TABLE),
        MagicMock(arrow=lambda: AGG_DAILY_TABLE),
    ]

    with patch("pipeline.assets.frontend_exports.pathlib.Path.exists", return_value=True), \
         patch("pipeline.assets.frontend_exports.duckdb.connect", return_value=mock_con):
        frontend_exports(
            pipeline_config=CONFIG,
            seaweedfs=mock_seaweedfs,
        )

    assert mock_seaweedfs.upload_parquet.call_count == 2
    upload_calls = mock_seaweedfs.upload_parquet.call_args_list
    keys = [c.kwargs["key"] for c in upload_calls]
    assert any("route_timeliness" in k for k in keys)
    assert any("daily_timeliness" in k for k in keys)
    buckets = [c.kwargs["bucket"] for c in upload_calls]
    assert all(b == CONFIG.export_bucket for b in buckets)


def test_frontend_exports_raises_on_missing_db():
    mock_seaweedfs = MagicMock()
    import pipeline.assets.frontend_exports as fe_mod

    original_fn = fe_mod.frontend_exports.op.compute_fn.decorated_fn
    with patch("pipeline.assets.frontend_exports.pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="DuckDB file not found"):
            original_fn(
                pipeline_config=CONFIG,
                seaweedfs=mock_seaweedfs,
            )
