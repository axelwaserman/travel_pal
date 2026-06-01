import pyarrow as pa
from datetime import date, timedelta
from dagster import asset
from pipeline.config import PipelineConfig


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

    combined = pa.concat_tables(tables)
    key = f"{pipeline_config.airport_icao}/raw_flights.parquet"
    seaweedfs.upload_parquet(combined, bucket=pipeline_config.raw_bucket, key=key)

    catalog = nessie.catalog
    if not catalog.table_exists("flights.raw_flights"):
        import pyiceberg.schema as sch
        from pyiceberg.types import NestedField, StringType, LongType

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
