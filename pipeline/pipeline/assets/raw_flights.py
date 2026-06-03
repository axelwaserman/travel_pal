import asyncio
import pyarrow as pa
import pyiceberg.schema as sch
from dagster import asset, ResourceParam
from pipeline.config import PipelineConfig
from pipeline.resources.opensky import OpenSkyAdapter
from pipeline.resources.nessie import NessieResource
from pyiceberg.types import NestedField, StringType, LongType


@asset
def raw_flights(
    pipeline_config: ResourceParam[PipelineConfig],
    opensky: ResourceParam[OpenSkyAdapter],
    nessie: ResourceParam[NessieResource],
) -> pa.Table:
    tables: list[pa.Table] = []

    async def _fetch_all() -> list[pa.Table]:
        departures = await opensky.fetch_departures(
            pipeline_config.airport_icao,
            pipeline_config.ingest_start_date,
            pipeline_config.ingest_end_date,
        )
        arrivals = await opensky.fetch_arrivals(
            pipeline_config.airport_icao,
            pipeline_config.ingest_start_date,
            pipeline_config.ingest_end_date,
        )
        return [departures, arrivals]

    tables = asyncio.run(_fetch_all())

    combined = pa.concat_tables(tables)

    if combined.num_rows == 0:
        return combined

    catalog = nessie.catalog
    if not catalog.table_exists("flights.raw_flights"):
        schema = sch.Schema(
            NestedField(1, "icao24", StringType(), required=False),
            NestedField(2, "callsign", StringType(), required=False),
            NestedField(3, "first_seen", LongType(), required=False),
            NestedField(4, "last_seen", LongType(), required=False),
            NestedField(5, "est_departure_airport", StringType(), required=False),
            NestedField(6, "est_arrival_airport", StringType(), required=False),
        )
        catalog.create_namespace_if_not_exists("flights")
        catalog.create_table("flights.raw_flights", schema=schema)

    table = catalog.load_table("flights.raw_flights")
    table.append(combined)

    return combined
