"""End-to-end BTS → Iceberg round-trip against real Nessie + SeaweedFS.

Uses the BTS fixture so no network call to transtats.bts.gov is made.
Infrastructure is provided by the ``infra_endpoints`` + ``seaweedfs_init``
session fixtures in conftest.py.
"""

from pathlib import Path

import pyarrow as pa
import pytest
from dagster import build_asset_context

from pipeline.assets.bts_on_time import bts_on_time
from pipeline.config import PipelineConfig
from pipeline.resources.bts import BTSResource
from pipeline.resources.nessie import NessieResource
from tests.integration._docker import DOCKER_AVAILABLE
from tests.integration._iceberg import InfraEndpoints, make_catalog

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bts_kjfk_2024_01.csv.zip"

_TABLE_IDENTIFIER = "flights.bts_on_time"

_SKIP_REASON = "Docker daemon is not reachable — skipping integration tests."
skip_if_no_docker = pytest.mark.skipif(not DOCKER_AVAILABLE, reason=_SKIP_REASON)


@pytest.mark.integration
@skip_if_no_docker
def test_bts_on_time_round_trip(
    infra_endpoints: InfraEndpoints,
    seaweedfs_init: None,
) -> None:
    """BTS fixture → bts_on_time asset → Iceberg flights.bts_on_time round trip."""
    nessie_resource = NessieResource(
        endpoint=infra_endpoints["nessie_uri"],
        s3_endpoint=infra_endpoints["s3_endpoint"],
        s3_access_key=infra_endpoints["s3_access_key"],
        s3_secret_key=infra_endpoints["s3_secret_key"],
    )

    # Idempotent teardown: drop table so repeated local runs don't accumulate rows.
    catalog = make_catalog(infra_endpoints)
    catalog.create_namespace_if_not_exists("flights")
    if catalog.table_exists(_TABLE_IDENTIFIER):
        catalog.drop_table(_TABLE_IDENTIFIER)

    config = PipelineConfig.model_validate(
        {
            "airport_icao": "KJFK",
            "ingest_start_date": "2024-01-01",
            "ingest_end_date": "2024-01-08",
            "SEAWEEDFS_S3_ENDPOINT": infra_endpoints["s3_endpoint"],
            "seaweedfs_access_key": infra_endpoints["s3_access_key"],
            "seaweedfs_secret_key": infra_endpoints["s3_secret_key"],
            "nessie_endpoint": infra_endpoints["nessie_uri"],
            "bts_fixture_file": str(FIXTURE),
        }
    )
    bts = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=str(FIXTURE),
    )

    ctx = build_asset_context(
        partition_key="2024-01",
        resources={
            "pipeline_config": config,
            "bts": bts,
            "nessie": nessie_resource,
        },
    )
    bts_on_time(ctx)

    iceberg_table = nessie_resource.catalog.load_table(_TABLE_IDENTIFIER)
    arrow_table: pa.Table = iceberg_table.scan().to_arrow()

    assert arrow_table.num_rows == 9, (
        f"Expected 9 KJFK rows from fixture; got {arrow_table.num_rows}"
    )

    schema_names = set(arrow_table.column_names)
    assert {
        "flight_date",
        "carrier_iata",
        "origin_iata",
        "destination_iata",
        "cancelled",
        "diverted",
        "year_month",
    }.issubset(schema_names), f"Missing expected columns; got {schema_names}"

    # Verify all 11 schema fields are present.
    expected_all = {
        "flight_date",
        "carrier_iata",
        "tail_number",
        "flight_number",
        "origin_iata",
        "destination_iata",
        "crs_dep_time",
        "cancelled",
        "cancellation_code",
        "diverted",
        "year_month",
    }
    assert expected_all == schema_names, (
        f"Schema mismatch. Expected {expected_all}, got {schema_names}"
    )

    year_months = set(arrow_table.column("year_month").to_pylist())
    assert year_months == {"2024-01"}, f"Expected year_month={{'2024-01'}}; got {year_months}"
