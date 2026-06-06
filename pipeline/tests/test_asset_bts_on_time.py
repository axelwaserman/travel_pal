from pathlib import Path
from unittest.mock import MagicMock

import pyarrow as pa
import pytest
from dagster import build_asset_context

from pipeline.assets.bts_on_time import bts_on_time
from pipeline.config import PipelineConfig

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bts_kjfk_2024_01.csv.zip"


def _make_config(tmp_path):
    return PipelineConfig.model_validate(
        {
            "airport_icao": "KJFK",
            "ingest_start_date": "2024-01-01",
            "ingest_end_date": "2024-01-08",
            "SEAWEEDFS_S3_ENDPOINT": "http://localhost:8333",
            "seaweedfs_access_key": "admin",
            "seaweedfs_secret_key": "admin",
            "nessie_endpoint": "http://localhost:19120/iceberg/",
            "bts_fixture_file": str(FIXTURE_PATH),
        }
    )


def _make_nessie_mock() -> MagicMock:
    """Return a nessie mock with update_schema context-manager wired up."""
    nessie = MagicMock()
    nessie.catalog.load_table.return_value.update_schema.return_value.__enter__ = lambda self: (
        MagicMock()
    )
    nessie.catalog.load_table.return_value.update_schema.return_value.__exit__ = lambda *args: None
    return nessie


@pytest.mark.unit
def test_bts_on_time_creates_table_and_appends_for_partition(tmp_path):
    """bts_on_time runs for partition '2024-01': filters to KJFK, creates the
    Iceberg table on first run, appends a non-empty PyArrow table.
    """
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    nessie = _make_nessie_mock()
    nessie.catalog.table_exists.return_value = False
    appended_tables: list[pa.Table] = []
    nessie.catalog.load_table.return_value.append = lambda t: appended_tables.append(t)

    ctx = build_asset_context(
        partition_key="2024-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
        },
    )

    bts_on_time(ctx)

    bts_resource.download_month.assert_called_once_with(2024, 1)
    nessie.catalog.create_namespace_if_not_exists.assert_called_once_with("flights")
    nessie.catalog.create_table.assert_called_once()
    assert len(appended_tables) == 1
    assert appended_tables[0].num_rows == 9  # KJFK rows in fixture


@pytest.mark.unit
def test_bts_on_time_no_op_on_zero_rows(tmp_path):
    """When the airport has no rows in this partition, asset returns without creating
    a table or appending — the empty table must not pollute Iceberg."""
    config = _make_config(tmp_path)

    # Hand back a ZIP that exists but has zero rows after filtering.
    empty_zip_path = tmp_path / "empty.zip"
    import zipfile as _zip

    with _zip.ZipFile(empty_zip_path, "w", compression=_zip.ZIP_DEFLATED) as zf:
        zf.writestr(
            "empty.csv",
            "FlightDate,Reporting_Airline,Tail_Number,Flight_Number_Reporting_Airline,"
            "Origin,Dest,CRSDepTime,Cancelled,CancellationCode,Diverted\n",
        )

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(empty_zip_path.read_bytes()))

    nessie = MagicMock()
    nessie.catalog.table_exists.return_value = False

    ctx = build_asset_context(
        partition_key="2024-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
        },
    )

    bts_on_time(ctx)

    nessie.catalog.create_table.assert_not_called()


@pytest.mark.unit
def test_bts_on_time_does_not_recreate_existing_table(tmp_path):
    """When the table already exists, the asset must not call create_table again."""
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    nessie = _make_nessie_mock()
    nessie.catalog.table_exists.return_value = True
    nessie.catalog.load_table.return_value.append = MagicMock()

    ctx = build_asset_context(
        partition_key="2024-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
        },
    )

    bts_on_time(ctx)

    nessie.catalog.create_table.assert_not_called()
    nessie.catalog.load_table.return_value.append.assert_called_once()


@pytest.mark.unit
def test_bts_on_time_calls_update_schema_before_append(tmp_path):
    """R6: union_by_name on update_schema must run before append so a
    schema-drift event can't drop columns silently.
    """
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    nessie = MagicMock()
    nessie.catalog.table_exists.return_value = True
    update_ctx = MagicMock()
    nessie.catalog.load_table.return_value.update_schema.return_value.__enter__ = lambda self: (
        update_ctx
    )
    nessie.catalog.load_table.return_value.update_schema.return_value.__exit__ = lambda *args: None

    ctx = build_asset_context(
        partition_key="2024-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
        },
    )

    bts_on_time(ctx)

    update_ctx.union_by_name.assert_called_once()
    nessie.catalog.load_table.return_value.append.assert_called_once()


def _async(value):
    """Return an already-resolved coroutine yielding ``value``."""

    async def _coro():
        return value

    return _coro()
