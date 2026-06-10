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

AGG_CARRIER_ROUTE_CANC = pa.table(
    {
        "origin_icao": ["KJFK"],
        "destination_icao": ["KLAX"],
        "carrier_icao": ["AAL"],
        "carrier_name": ["American Airlines"],
        "total_scheduled": [500],
        "cancelled": [25],
        "cancellation_rate": [0.05],
        "period_start": pa.array([date(2024, 1, 1)], type=pa.date32()),
        "period_end": pa.array([date(2024, 12, 31)], type=pa.date32()),
    }
)

AGG_ROUTE_CANC_REASONS = pa.table(
    {
        "origin_icao": ["KJFK"],
        "destination_icao": ["KLAX"],
        "reason": ["Weather"],
        "cancelled_count": [15],
        "reason_share": [0.6],
    }
)

DIM_AIRPORT = pa.table(
    {
        "icao": ["KJFK", "KLAX"],
        "iata": ["JFK", "LAX"],
        "name": ["John F Kennedy Intl", "Los Angeles Intl"],
        "city": ["New York", "Los Angeles"],
        "country": ["US", "US"],
        "lat": [40.6413, 33.9425],
        "lon": [-73.7781, -118.4081],
        "airport_type": ["large_airport", "large_airport"],
    }
)

DIM_CARRIER = pa.table(
    {
        "icao": ["AAL", "UAL"],
        "iata": ["AA", "UA"],
        "name": ["American Airlines", "United Airlines"],
        "callsign": ["AMERICAN", "UNITED"],
        "country": ["US", "US"],
        "active": ["Y", "Y"],
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
    # Six read_parquet calls: 4 original marts + 2 new P2.3 marts.
    # Dim reads go through _read_dbt_table (patched separately).
    mock_con.execute.side_effect = _mart_execute_side_effects()

    with (
        patch("pipeline.assets.frontend_exports.duckdb.connect", return_value=mock_con),
        _patch_dims(),
    ):
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

    # Validate uploads — 6 per-airport + 2 root dims = 8 total
    assert mock_seaweedfs.upload_parquet.call_count == 8
    upload_calls = mock_seaweedfs.upload_parquet.call_args_list
    keys = [c.kwargs["key"] for c in upload_calls]
    assert "KJFK/route_timeliness.parquet" in keys
    assert "KJFK/daily_timeliness.parquet" in keys
    assert "KJFK/carrier_cancellations.parquet" in keys
    assert "KJFK/route_cancellations.parquet" in keys
    assert "KJFK/carrier_route_cancellations.parquet" in keys
    assert "KJFK/route_cancellation_reasons.parquet" in keys
    assert "dim_airport.parquet" in keys
    assert "dim_carrier.parquet" in keys
    buckets = {c.kwargs["bucket"] for c in upload_calls}
    assert buckets == {"frontend-exports"}
    # Validate the arrow table from DuckDB reaches upload_parquet (regression: .arrow() vs .to_arrow_table())
    uploaded_tables = [c.args[0] for c in upload_calls]
    assert AGG_ROUTE_TABLE in uploaded_tables
    assert AGG_DAILY_TABLE in uploaded_tables
    assert AGG_CARRIER_CANC in uploaded_tables
    assert AGG_ROUTE_CANC in uploaded_tables


def _patch_dims() -> "patch":
    """Patch _read_dbt_table to return stub dim tables without touching disk."""
    return patch(
        "pipeline.assets.frontend_exports._read_dbt_table",
        side_effect=lambda ref: {
            "main_ref.dim_airport": DIM_AIRPORT,
            "main_ref.dim_carrier": DIM_CARRIER,
        }[ref],
    )


def _mart_execute_side_effects() -> list[MagicMock]:
    """7 setup calls + 6 mart read_parquet calls for the :memory: connection."""
    return [MagicMock() for _ in range(7)] + [
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_DAILY_TABLE),
        MagicMock(to_arrow_table=lambda: AGG_CARRIER_CANC),
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_CANC),
        MagicMock(to_arrow_table=lambda: AGG_CARRIER_ROUTE_CANC),
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_CANC_REASONS),
    ]


def test_frontend_exports_strips_scheme_from_endpoint():
    """seaweedfs_endpoint comes in as 'http://...'; SET s3_endpoint must be bare host:port."""
    config = _make_config()  # endpoint='http://localhost:8333'
    mock_seaweedfs = MagicMock()
    mock_con = MagicMock()
    mock_con.__enter__ = lambda s: mock_con
    mock_con.__exit__ = MagicMock(return_value=False)
    mock_con.execute.side_effect = _mart_execute_side_effects()

    with (
        patch("pipeline.assets.frontend_exports.duckdb.connect", return_value=mock_con),
        _patch_dims(),
    ):
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
    mock_con.execute.side_effect = _mart_execute_side_effects()

    with (
        patch("pipeline.assets.frontend_exports.duckdb.connect", return_value=mock_con),
        _patch_dims(),
    ):
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


def test_frontend_exports_emits_6_per_airport_parquets_and_2_dim_parquets_at_root():
    """frontend_exports must:
    - Upload 6 parquets under KJFK/ (4 existing + 2 new P2.3 marts)
    - Upload 2 dim parquets at the bucket root (no KJFK/ prefix)
    - Dim queries must have no WHERE clause (full table export)
    - New P2.3 mart queries must filter by origin OR destination
    """
    config = _make_config()
    mock_seaweedfs = MagicMock()

    # ---- S3 / :memory: connection (mart reads) ----
    mock_s3_con = MagicMock()
    mock_s3_con.__enter__ = lambda s: mock_s3_con
    mock_s3_con.__exit__ = MagicMock(return_value=False)
    mock_s3_con.execute.side_effect = [
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
        MagicMock(to_arrow_table=lambda: AGG_CARRIER_ROUTE_CANC),
        MagicMock(to_arrow_table=lambda: AGG_ROUTE_CANC_REASONS),
    ]

    # ---- dbt DuckDB connection (dim reads) ----
    mock_dbt_con = MagicMock()
    mock_dbt_con.__enter__ = lambda s: mock_dbt_con
    mock_dbt_con.__exit__ = MagicMock(return_value=False)
    mock_dbt_con.execute.side_effect = [
        MagicMock(to_arrow_table=lambda: DIM_AIRPORT),
        MagicMock(to_arrow_table=lambda: DIM_CARRIER),
    ]

    def _connect_side_effect(path: str) -> MagicMock:
        if path == ":memory:":
            return mock_s3_con
        return mock_dbt_con

    with patch(
        "pipeline.assets.frontend_exports.duckdb.connect",
        side_effect=_connect_side_effect,
    ):
        frontend_exports(pipeline_config=config, seaweedfs=mock_seaweedfs)

    # --- 8 total uploads: 6 per-airport + 2 root dims ---
    assert mock_seaweedfs.upload_parquet.call_count == 8

    upload_calls = mock_seaweedfs.upload_parquet.call_args_list
    keys = [c.kwargs["key"] for c in upload_calls]

    # Per-airport parquets (6)
    assert "KJFK/route_timeliness.parquet" in keys
    assert "KJFK/daily_timeliness.parquet" in keys
    assert "KJFK/carrier_cancellations.parquet" in keys
    assert "KJFK/route_cancellations.parquet" in keys
    assert "KJFK/carrier_route_cancellations.parquet" in keys
    assert "KJFK/route_cancellation_reasons.parquet" in keys

    # Dim parquets at ROOT (no airport prefix)
    assert "dim_airport.parquet" in keys
    assert "dim_carrier.parquet" in keys

    # Dims must NOT land under KJFK/
    assert "KJFK/dim_airport.parquet" not in keys
    assert "KJFK/dim_carrier.parquet" not in keys

    # All uploads target the frontend-exports bucket
    buckets = {c.kwargs["bucket"] for c in upload_calls}
    assert buckets == {"frontend-exports"}

    # --- S3 mart queries include WHERE predicate ---
    s3_read_calls = [c for c in mock_s3_con.execute.call_args_list if "read_parquet" in c.args[0]]
    carrier_route_call = next(
        c for c in s3_read_calls if "agg_carrier_route_cancellations" in c.args[0]
    )
    reason_call = next(c for c in s3_read_calls if "agg_route_cancellation_reasons" in c.args[0])
    assert (
        "WHERE origin_icao = $airport OR destination_icao = $airport" in carrier_route_call.args[0]
    )
    assert "WHERE origin_icao = $airport OR destination_icao = $airport" in reason_call.args[0]
    assert carrier_route_call.args[1] == {"airport": "KJFK"}
    assert reason_call.args[1] == {"airport": "KJFK"}

    # --- Dim queries have NO WHERE clause ---
    dbt_calls = mock_dbt_con.execute.call_args_list
    dim_airport_call = next(c for c in dbt_calls if "dim_airport" in c.args[0])
    dim_carrier_call = next(c for c in dbt_calls if "dim_carrier" in c.args[0])
    assert "WHERE" not in dim_airport_call.args[0]
    assert "WHERE" not in dim_carrier_call.args[0]
