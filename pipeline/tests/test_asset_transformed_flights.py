from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from pipeline.assets.frontend_exports import frontend_exports
from pipeline.assets.transformed_flights import transformed_flights
from pipeline.config import PipelineConfig


def _make_config() -> PipelineConfig:
    return PipelineConfig.model_validate(
        {
            "airport_icao": "KJFK",
            "ingest_start_date": "2024-01-01",
            "ingest_end_date": "2024-01-08",
            "SEAWEEDFS_S3_ENDPOINT": "http://localhost:8333",
            "seaweedfs_access_key": "admin",
            "seaweedfs_secret_key": "admin",
            "nessie_endpoint": "http://localhost:19120/api/v1",
        }
    )


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


def test_frontend_exports_reads_marts_from_s3():
    config = _make_config()
    mock_seaweedfs = MagicMock()
    mock_con = MagicMock()
    mock_con.__enter__ = lambda s: mock_con
    mock_con.__exit__ = MagicMock(return_value=False)
    # Two read_parquet calls, one per mart
    mock_con.execute.side_effect = [
        MagicMock(),  # INSTALL httpfs
        MagicMock(),  # LOAD httpfs
        MagicMock(),  # SET s3_endpoint
        MagicMock(),  # SET s3_access_key_id
        MagicMock(),  # SET s3_secret_access_key
        MagicMock(),  # SET s3_use_ssl
        MagicMock(),  # SET s3_url_style
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_DAILY_TABLE),
    ]

    with patch("pipeline.assets.frontend_exports.duckdb.connect", return_value=mock_con):
        frontend_exports(
            pipeline_config=config,
            seaweedfs=mock_seaweedfs,
        )

    # Validate both reads pointed at S3
    executed_sql = [c.args[0] for c in mock_con.execute.call_args_list]
    assert any(
        "read_parquet('s3://raw-flights/warehouse/marts/agg_route_timeliness.parquet')" in s
        for s in executed_sql
    )
    assert any(
        "read_parquet('s3://raw-flights/warehouse/marts/agg_daily_timeliness.parquet')" in s
        for s in executed_sql
    )

    # Validate uploads
    assert mock_seaweedfs.upload_parquet.call_count == 2
    upload_calls = mock_seaweedfs.upload_parquet.call_args_list
    keys = [c.kwargs["key"] for c in upload_calls]
    assert "KJFK/route_timeliness.parquet" in keys
    assert "KJFK/daily_timeliness.parquet" in keys
    buckets = {c.kwargs["bucket"] for c in upload_calls}
    assert buckets == {"frontend-exports"}
    # Validate the arrow table from DuckDB reaches upload_parquet (regression: .arrow() vs .to_arrow_table())
    uploaded_tables = [c.args[0] for c in upload_calls]
    assert AGG_ROUTE_TABLE in uploaded_tables
    assert AGG_DAILY_TABLE in uploaded_tables


def test_frontend_exports_strips_scheme_from_endpoint():
    """seaweedfs_endpoint comes in as 'http://...'; SET s3_endpoint must be bare host:port."""
    config = _make_config()  # endpoint='http://localhost:8333'
    mock_seaweedfs = MagicMock()
    mock_con = MagicMock()
    mock_con.__enter__ = lambda s: mock_con
    mock_con.__exit__ = MagicMock(return_value=False)
    mock_con.execute.side_effect = [MagicMock() for _ in range(7)] + [
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_DAILY_TABLE),
    ]

    with patch("pipeline.assets.frontend_exports.duckdb.connect", return_value=mock_con):
        frontend_exports(pipeline_config=config, seaweedfs=mock_seaweedfs)

    set_calls = [
        c.args[0]
        for c in mock_con.execute.call_args_list
        if c.args[0].startswith("SET s3_endpoint")
    ]
    assert len(set_calls) == 1
    assert "http://" not in set_calls[0]
    assert "localhost:8333" in set_calls[0]
