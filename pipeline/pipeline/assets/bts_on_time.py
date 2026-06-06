"""BTS On-Time Performance Dagster asset.

Monthly-partitioned: each partition_key is 'YYYY-MM' and lands rows for that
month into Iceberg flights.bts_on_time. Only rows where origin OR destination
matches the configured airport_icao (translated through OurAirports IATA→ICAO
in the staging model) are written to keep the raw table compact.

Schema is created on first run; subsequent partitions append. PyIceberg's
`update_schema` API is used idempotently before append in case the column set
ever evolves (R6 in the spec).
"""

import asyncio

import pyiceberg.schema as sch
from dagster import (
    AssetExecutionContext,
    MonthlyPartitionsDefinition,
    ResourceParam,
    asset,
)
from pyiceberg.types import BooleanType, DateType, NestedField, StringType

from pipeline.config import PipelineConfig
from pipeline.resources.bts import BTSResource, extract_csv_from_zip
from pipeline.resources.nessie import NessieResource
from pipeline.resources.seaweedfs import SeaweedFSResource

BTS_PARTITIONS = MonthlyPartitionsDefinition(start_date="2024-01-01")

_TABLE_IDENTIFIER = "flights.bts_on_time"

_SCHEMA = sch.Schema(
    NestedField(1, "flight_date", DateType(), required=False),
    NestedField(2, "carrier_iata", StringType(), required=False),
    NestedField(3, "tail_number", StringType(), required=False),
    NestedField(4, "flight_number", StringType(), required=False),
    NestedField(5, "origin_iata", StringType(), required=False),
    NestedField(6, "destination_iata", StringType(), required=False),
    NestedField(7, "crs_dep_time", StringType(), required=False),
    NestedField(8, "cancelled", BooleanType(), required=False),
    NestedField(9, "cancellation_code", StringType(), required=False),
    NestedField(10, "diverted", BooleanType(), required=False),
    NestedField(11, "year_month", StringType(), required=False),
)


def _airport_iata(airport_icao: str) -> str:
    """Phase 1 demo airport is hardcoded to KJFK→JFK; the staging dim_airport
    lookup handles the general case at SQL time. Asset-level filter just
    needs the IATA prefix to keep the raw table small.
    """
    if airport_icao.upper() == "KJFK":
        return "JFK"
    # Fallback: strip the leading 'K' for US airports, otherwise pass through.
    if airport_icao.startswith("K") and len(airport_icao) == 4:
        return airport_icao[1:]
    return airport_icao


@asset(partitions_def=BTS_PARTITIONS)
def bts_on_time(
    context: AssetExecutionContext,
    pipeline_config: ResourceParam[PipelineConfig],
    bts: ResourceParam[BTSResource],
    nessie: ResourceParam[NessieResource],
    seaweedfs: ResourceParam[SeaweedFSResource],
) -> None:
    year_str, month_str = context.partition_key.split("-")
    year = int(year_str)
    month = int(month_str)

    cache_key = f"{context.partition_key}.zip"
    try:
        zip_bytes = seaweedfs.get_object(
            bucket=pipeline_config.bts_cache_bucket,
            key=cache_key,
        )
        context.log.info(
            f"BTS partition {context.partition_key} loaded from cache "
            f"s3://{pipeline_config.bts_cache_bucket}/{cache_key}"
        )
    except FileNotFoundError:
        zip_bytes = asyncio.run(bts.download_month(year, month))
        seaweedfs.put_object(
            bucket=pipeline_config.bts_cache_bucket,
            key=cache_key,
            body=zip_bytes,
        )
        context.log.info(
            f"BTS partition {context.partition_key} downloaded and cached "
            f"to s3://{pipeline_config.bts_cache_bucket}/{cache_key}"
        )

    table = extract_csv_from_zip(
        zip_bytes,
        origin_iata=_airport_iata(pipeline_config.airport_icao),
    )

    if table.num_rows == 0:
        context.log.info(
            f"BTS partition {context.partition_key} produced 0 rows for "
            f"airport {pipeline_config.airport_icao}; skipping append"
        )
        return

    # Cast flight_date string → date32 for Iceberg DateType.
    import pyarrow as pa
    import pyarrow.compute as pc

    flight_date_str = table.column("flight_date")
    flight_date_date = pc.cast(
        pc.strptime(  # ty: ignore[unresolved-attribute]  # pyarrow.compute stubs incomplete
            flight_date_str, format="%Y-%m-%d", unit="s"
        ),
        pa.date32(),
    )
    table = table.set_column(
        table.column_names.index("flight_date"),
        "flight_date",
        flight_date_date,
    )

    catalog = nessie.catalog
    catalog.create_namespace_if_not_exists("flights")
    if not catalog.table_exists(_TABLE_IDENTIFIER):
        catalog.create_table(_TABLE_IDENTIFIER, schema=_SCHEMA)

    iceberg_table = catalog.load_table(_TABLE_IDENTIFIER)
    # R6: schema-drift safety. update_schema() is a no-op when the table
    # schema already matches the local _SCHEMA, so this is cheap and prevents
    # silent column drops if the local schema gains a field later.
    with iceberg_table.update_schema() as upd:
        upd.union_by_name(_SCHEMA)
    iceberg_table.append(table)

    context.log.info(
        f"Appended {table.num_rows} BTS rows for {context.partition_key} to {_TABLE_IDENTIFIER}"
    )
