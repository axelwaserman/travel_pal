import pyarrow as pa
import pyiceberg.schema as sch
from datetime import date, timedelta
from dagster import asset
from pipeline.config import PipelineConfig
from pyiceberg.types import NestedField, StringType, LongType


def _date_chunks(start: str, end: str, days: int = 7):
    current = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    while current < end_date:
        chunk_end = min(current + timedelta(days=days), end_date)
        yield current.isoformat(), chunk_end.isoformat()
        current = chunk_end


@asset
def raw_flights(
    pipeline_config: PipelineConfig,
    opensky,
    seaweedfs,
    nessie,
) -> pa.Table:
    tables: list[pa.Table] = []

    for chunk_start, chunk_end in _date_chunks(
        pipeline_config.ingest_start_date, pipeline_config.ingest_end_date
    ):
        departures = opensky.fetch_departures(
            pipeline_config.airport_icao, chunk_start, chunk_end
        )
        arrivals = opensky.fetch_arrivals(
            pipeline_config.airport_icao, chunk_start, chunk_end
        )
        tables.extend([departures, arrivals])

    if not tables:
        return pa.table({
            "icao24": pa.array([], type=pa.string()),
            "callsign": pa.array([], type=pa.string()),
            "first_seen": pa.array([], type=pa.int64()),
            "last_seen": pa.array([], type=pa.int64()),
            "est_departure_airport": pa.array([], type=pa.string()),
            "est_arrival_airport": pa.array([], type=pa.string()),
        })

    combined = pa.concat_tables(tables)
    key = f"{pipeline_config.airport_icao}/raw_flights.parquet"
    seaweedfs.upload_parquet(combined, bucket=pipeline_config.raw_bucket, key=key)

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

    return combined
