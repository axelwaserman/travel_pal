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

    seaweedfs_mock = MagicMock()
    seaweedfs_mock.get_object.side_effect = FileNotFoundError("no cache")

    ctx = build_asset_context(
        partition_key="2024-01-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
            "seaweedfs": seaweedfs_mock,
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

    seaweedfs_mock = MagicMock()
    seaweedfs_mock.get_object.side_effect = FileNotFoundError("no cache")

    ctx = build_asset_context(
        partition_key="2024-01-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
            "seaweedfs": seaweedfs_mock,
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

    seaweedfs_mock = MagicMock()
    seaweedfs_mock.get_object.side_effect = FileNotFoundError("no cache")

    ctx = build_asset_context(
        partition_key="2024-01-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
            "seaweedfs": seaweedfs_mock,
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

    seaweedfs_mock = MagicMock()
    seaweedfs_mock.get_object.side_effect = FileNotFoundError("no cache")

    ctx = build_asset_context(
        partition_key="2024-01-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
            "seaweedfs": seaweedfs_mock,
        },
    )

    bts_on_time(ctx)

    update_ctx.union_by_name.assert_called_once()
    nessie.catalog.load_table.return_value.append.assert_called_once()


@pytest.mark.unit
def test_bts_on_time_uses_seaweedfs_cache_when_present(tmp_path):
    """When SeaweedFS already holds a cached BTS ZIP for this partition,
    the asset must read from the cache and NOT call BTSResource.download_month.
    """
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    seaweedfs = MagicMock()
    seaweedfs.get_object.return_value = FIXTURE_PATH.read_bytes()

    nessie = _make_nessie_mock()
    nessie.catalog.table_exists.return_value = True

    ctx = build_asset_context(
        partition_key="2024-01-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
            "seaweedfs": seaweedfs,
        },
    )
    bts_on_time(ctx)

    bts_resource.download_month.assert_not_called()
    seaweedfs.get_object.assert_called_once_with(bucket="bts-raw", key="2024-01.zip")


@pytest.mark.unit
def test_bts_on_time_writes_to_cache_after_download(tmp_path):
    """When SeaweedFS does not have a cached ZIP, asset downloads from BTS,
    writes the bytes to seaweedfs.put_object, then proceeds with append.
    """
    config = _make_config(tmp_path)

    bts_resource = MagicMock()
    bts_resource.download_month = MagicMock(return_value=_async(FIXTURE_PATH.read_bytes()))

    seaweedfs = MagicMock()
    seaweedfs.get_object.side_effect = FileNotFoundError("no cache")

    nessie = _make_nessie_mock()
    nessie.catalog.table_exists.return_value = True

    ctx = build_asset_context(
        partition_key="2024-01-01",
        resources={
            "pipeline_config": config,
            "bts": bts_resource,
            "nessie": nessie,
            "seaweedfs": seaweedfs,
        },
    )
    bts_on_time(ctx)

    bts_resource.download_month.assert_called_once_with(2024, 1)
    seaweedfs.put_object.assert_called_once()
    args = seaweedfs.put_object.call_args.kwargs
    assert args["bucket"] == "bts-raw"
    assert args["key"] == "2024-01.zip"
    assert args["body"][:2] == b"PK"


def _async(value):
    """Return an already-resolved coroutine yielding ``value``."""

    async def _coro():
        return value

    return _coro()
