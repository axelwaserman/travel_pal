"""Shared Iceberg fixture helpers for integration tests.

Centralises the catalog factory, the canonical ``raw_flights`` schema, and the
``InfraEndpoints`` typed mapping shape so both ``test_integration_iceberg.py``
and ``test_integration_dbt_build.py`` consume a single source of truth.

The schema mirrors the production table written by
``pipeline/pipeline/assets/raw_flights.py`` (same field IDs, types, and
required flags). Keep them in lock-step.
"""

from typing import TypedDict

from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType


class InfraEndpoints(TypedDict):
    """Endpoint mapping yielded by the ``infra_endpoints`` session fixture.

    Keys mirror the dict returned by ``conftest.infra_endpoints`` and the
    keyword arguments consumed by ``RestCatalog`` and the dbt env block.
    """

    nessie_uri: str
    warehouse: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str


# Mirrors the production ``raw_flights`` Iceberg schema declared in
# ``pipeline/pipeline/assets/raw_flights.py``. Field IDs, types, and required
# flags must stay in lock-step with the asset.
RAW_FLIGHTS_SCHEMA: Schema = Schema(
    NestedField(1, "icao24", StringType(), required=False),
    NestedField(2, "callsign", StringType(), required=False),
    NestedField(3, "first_seen", LongType(), required=False),
    NestedField(4, "last_seen", LongType(), required=False),
    NestedField(5, "est_departure_airport", StringType(), required=False),
    NestedField(6, "est_arrival_airport", StringType(), required=False),
)


def make_catalog(endpoints: InfraEndpoints) -> RestCatalog:
    """Build a RestCatalog pointing at the live Nessie + SeaweedFS stack.

    PyIceberg's ``RestCatalog.url()`` appends ``/v1/`` to the supplied uri,
    so ``http://host:19120/iceberg/`` becomes ``http://host:19120/iceberg/v1/...``,
    which matches Nessie's Iceberg REST Catalog namespace.
    """
    return RestCatalog(
        name="nessie",
        **{
            "uri": endpoints["nessie_uri"],
            "warehouse": endpoints["warehouse"],
            "s3.endpoint": endpoints["s3_endpoint"],
            "s3.access-key-id": endpoints["s3_access_key"],
            "s3.secret-access-key": endpoints["s3_secret_key"],
            "s3.path-style-access": "true",
            "s3.region": "us-east-1",
        },
    )
