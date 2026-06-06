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

AGG_CARRIER_CANC = pa.table(
    {
        "origin_icao": ["KJFK"],
        "carrier_icao": ["AAL"],
        "carrier_name": ["American Airlines"],
        "total_scheduled": [1000],
        "cancelled": [50],
        "cancellation_rate": [0.05],
        "period_start": pa.array([date(2024, 1, 1)], type=pa.date32()),
        "period_end": pa.array([date(2024, 12, 31)], type=pa.date32()),
    }
)

AGG_ROUTE_CANC = pa.table(
    {
        "origin_icao": ["KJFK"],
        "destination_icao": ["KLAX"],
        "total_scheduled": [800],
        "cancelled": [40],
        "cancellation_rate": [0.05],
        "period_start": pa.array([date(2024, 1, 1)], type=pa.date32()),
        "period_end": pa.array([date(2024, 12, 31)], type=pa.date32()),
    }
)


def test_transformed_flights_depends_on_bts_on_time():
    """transformed_flights must declare an AssetIn for bts_on_time so dbt build
    waits for the BTS partition to land before executing.
    """
    from pipeline.assets.transformed_flights import transformed_flights as asset_fn

    deps = {ak.to_user_string() for ak in asset_fn.dependency_keys}
    assert "bts_on_time" in deps, f"transformed_flights deps missing bts_on_time; have {deps}"


def test_transformed_flights_runs_dbt():
    mock_seaweedfs = MagicMock()
    with patch("pipeline.assets.transformed_flights.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        transformed_flights(
            pipeline_config=CONFIG,
            raw_flights=pa.table({"icao24": ["x"]}),
            seaweedfs=mock_seaweedfs,
        )
    assert mock_run.call_count == 2
    seed_call, run_call = mock_run.call_args_list
    assert seed_call.args[0][1] == "seed"
    assert run_call.args[0][1] == "run"
    cmd = run_call.args[0]
    assert "dbt" in cmd
    assert "--project-dir" in cmd
    project_dir_idx = cmd.index("--project-dir") + 1
    assert cmd[project_dir_idx].endswith("/transforms")
    assert Path(cmd[project_dir_idx]).is_absolute()
    # no cwd kwarg — path is absolute so cwd is not needed
    assert "cwd" not in (run_call.kwargs or {})


@pytest.mark.parametrize(
    "failing_step,expected_msg",
    [
        ("seed", "dbt seed failed"),
        ("run", "dbt run failed"),
    ],
)
def test_transformed_flights_raises_when_dbt_step_fails(
    failing_step: str, expected_msg: str
) -> None:
    mock_seaweedfs = MagicMock()

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        if cmd[1] == failing_step:
            return MagicMock(returncode=1, stdout="", stderr="boom")
        return MagicMock(returncode=0)

    with patch("pipeline.assets.transformed_flights.subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match=expected_msg):
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
    # Four read_parquet calls, one per mart
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
        MagicMock(to_arrow_table=lambda: AGG_CARRIER_CANC),
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_CANC),
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

    # Validate per-mart airport predicate is wired and parameter is bound to airport_icao.
    # Daily mart filters on origin_icao only; route mart filters on either side.
    read_calls = [c for c in mock_con.execute.call_args_list if "read_parquet" in c.args[0]]
    daily_call = next(c for c in read_calls if "agg_daily_timeliness" in c.args[0])
    route_call = next(c for c in read_calls if "agg_route_timeliness" in c.args[0])

    assert "WHERE origin_icao = $airport" in daily_call.args[0]
    assert "destination_icao" not in daily_call.args[0].split("WHERE", 1)[1], (
        "daily mart predicate must not include destination_icao — the mart only "
        "carries origin_icao, so a destination filter would always be false"
    )
    assert daily_call.args[1] == {"airport": "KJFK"}

    assert "WHERE origin_icao = $airport OR destination_icao = $airport" in route_call.args[0]
    assert route_call.args[1] == {"airport": "KJFK"}

    # Validate uploads
    assert mock_seaweedfs.upload_parquet.call_count == 4
    upload_calls = mock_seaweedfs.upload_parquet.call_args_list
    keys = [c.kwargs["key"] for c in upload_calls]
    assert "KJFK/route_timeliness.parquet" in keys
    assert "KJFK/daily_timeliness.parquet" in keys
    assert "KJFK/carrier_cancellations.parquet" in keys
    assert "KJFK/route_cancellations.parquet" in keys
    buckets = {c.kwargs["bucket"] for c in upload_calls}
    assert buckets == {"frontend-exports"}
    # Validate the arrow table from DuckDB reaches upload_parquet (regression: .arrow() vs .to_arrow_table())
    uploaded_tables = [c.args[0] for c in upload_calls]
    assert AGG_ROUTE_TABLE in uploaded_tables
    assert AGG_DAILY_TABLE in uploaded_tables
    assert AGG_CARRIER_CANC in uploaded_tables
    assert AGG_ROUTE_CANC in uploaded_tables


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
        MagicMock(to_arrow_table=lambda: AGG_CARRIER_CANC),
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_CANC),
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


def test_frontend_exports_includes_cancellation_marts():
    """frontend_exports must read both cancellation marts and upload them under
    the airport-namespaced keys carrier_cancellations.parquet + route_cancellations.parquet.
    """
    config = _make_config()
    mock_seaweedfs = MagicMock()
    mock_con = MagicMock()
    mock_con.__enter__ = lambda s: mock_con
    mock_con.__exit__ = MagicMock(return_value=False)
    mock_con.execute.side_effect = [MagicMock() for _ in range(7)] + [
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_DAILY_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_CARRIER_CANC),
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_CANC),
    ]

    with patch("pipeline.assets.frontend_exports.duckdb.connect", return_value=mock_con):
        frontend_exports(pipeline_config=config, seaweedfs=mock_seaweedfs)

    keys = [c.kwargs["key"] for c in mock_seaweedfs.upload_parquet.call_args_list]
    assert "KJFK/carrier_cancellations.parquet" in keys
    assert "KJFK/route_cancellations.parquet" in keys

    read_calls = [c for c in mock_con.execute.call_args_list if "read_parquet" in c.args[0]]
    carrier_call = next(c for c in read_calls if "agg_carrier_cancellations" in c.args[0])
    route_canc_call = next(c for c in read_calls if "agg_route_cancellations" in c.args[0])
    assert "WHERE origin_icao = $airport" in carrier_call.args[0]
    assert "WHERE origin_icao = $airport OR destination_icao = $airport" in route_canc_call.args[0]
    assert carrier_call.args[1] == {"airport": "KJFK"}
    assert route_canc_call.args[1] == {"airport": "KJFK"}
