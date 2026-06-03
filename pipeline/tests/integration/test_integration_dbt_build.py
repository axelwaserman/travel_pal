"""Integration test: fixture → Iceberg → dbt build → S3 parquet round-trip.

Harness shape
-------------
1. ``infra_endpoints`` + ``seaweedfs_init`` fixtures spin up (or reuse) a live
   Nessie 0.104.4 + SeaweedFS S3 stack.
2. The ``flights.raw_flights`` Iceberg table is populated via the direct catalog
   path (RestCatalog + pyarrow) rather than by invoking the Dagster asset.  The
   direct path was chosen over ``dagster asset materialize`` because it avoids
   bringing up the full Dagster resource graph (postgres, webserver) inside a
   pytest process, keeps the test self-contained, and exercises exactly the same
   S3/Nessie write path that the production asset uses — only the HTTP client
   layer is bypassed.  The trade-off is documented here so it can be revisited
   when a lightweight ``dagster asset materialize --select raw_flights`` path
   becomes practical in CI without Postgres.
3. After pyiceberg writes data it mirrors the Iceberg table to the canonical
   ``raw_flights`` S3 path (without UUID suffix) so that DuckDB's
   ``iceberg_scan`` — which uses a hardcoded path in ``stg_flights.sql`` — can
   locate the table.  Background: Nessie's REST catalog always appends a UUID to
   the table directory name; DuckDB's iceberg extension reads via the object
   storage path directly and cannot consult the Nessie catalog for resolution.
   The mirroring step decodes ``aws-chunked`` encoding that ``aiobotocore`` adds
   to PUT requests (stored verbatim by SeaweedFS), then copies all metadata and
   data files to ``raw_flights/``.  A ``version-hint.text`` + ``v1.metadata.json``
   allow DuckDB to resolve the current snapshot without globbing.
4. ``dbt build`` is invoked via subprocess against ``pipeline/transforms/`` with
   ``DBT_DUCKDB_PATH`` pointing at a test-scoped tmp file so runs never collide.
5. Assertions:
   - ``dbt build`` returncode == 0.
   - ``stg_flights`` view exists in the DuckDB target and has rows.
   - ``agg_daily_timeliness`` parquet was written to S3 and has rows when read
     back via DuckDB + httpfs.

Marked ``@pytest.mark.integration``.  Skipped automatically when Docker is not
available (reuses ``skip_if_no_docker`` from ``test_integration_iceberg.py``)
or when ``dbt`` is not on PATH.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import boto3
import duckdb
import pyarrow as pa
import pytest
from botocore.config import Config
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType

from tests.integration._docker import DOCKER_AVAILABLE

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).parent.parent.parent.parent  # …/travel_pal
_TRANSFORMS_DIR: Path = _REPO_ROOT / "pipeline" / "transforms"
_FIXTURES_DIR: Path = _REPO_ROOT / "pipeline" / "tests" / "fixtures"

# The S3 path that stg_flights.sql hard-codes for iceberg_scan().
_RAW_FLIGHTS_CANONICAL_S3_KEY: str = "warehouse/flights/raw_flights"
_RAW_FLIGHTS_CANONICAL_LOCATION: str = (
    "s3://raw-flights/" + _RAW_FLIGHTS_CANONICAL_S3_KEY
)

# ---------------------------------------------------------------------------
# Iceberg schema — mirrors production raw_flights table in raw_flights.py
# ---------------------------------------------------------------------------

_RAW_FLIGHTS_SCHEMA: Schema = Schema(
    NestedField(1, "icao24", StringType(), required=False),
    NestedField(2, "callsign", StringType(), required=False),
    NestedField(3, "first_seen", LongType(), required=False),
    NestedField(4, "last_seen", LongType(), required=False),
    NestedField(5, "est_departure_airport", StringType(), required=False),
    NestedField(6, "est_arrival_airport", StringType(), required=False),
)

# ---------------------------------------------------------------------------
# Skip guards
# ---------------------------------------------------------------------------

_SKIP_NO_DOCKER = "Docker daemon is not reachable — skipping integration tests."
skip_if_no_docker = pytest.mark.skipif(not DOCKER_AVAILABLE, reason=_SKIP_NO_DOCKER)

_SKIP_NO_DBT = "dbt is not on PATH — skipping dbt build integration test."
skip_if_no_dbt = pytest.mark.skipif(
    shutil.which("dbt") is None,
    reason=_SKIP_NO_DBT,
)

# ---------------------------------------------------------------------------
# S3 client helpers
# ---------------------------------------------------------------------------


def _make_s3_client(endpoints: dict[str, str]) -> Any:
    """Return a boto3 S3 client pointed at the test SeaweedFS endpoint."""
    return boto3.client(
        "s3",
        endpoint_url=endpoints["s3_endpoint"],
        aws_access_key_id=endpoints["s3_access_key"],
        aws_secret_access_key=endpoints["s3_secret_key"],
        config=Config(s3={"addressing_style": "path"}),
        region_name="us-east-1",
    )


# ---------------------------------------------------------------------------
# Iceberg catalog helper
# ---------------------------------------------------------------------------


def _build_catalog(endpoints: dict[str, str]) -> RestCatalog:
    """Return a RestCatalog wired to the live Nessie + SeaweedFS stack."""
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


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------


def _load_fixture_as_arrow(filename: str) -> pa.Table:
    """Read a JSON fixture file and return it as a PyArrow table.

    The fixture JSON uses OpenSky camelCase field names; this function maps
    them to the snake_case schema expected by the Iceberg raw_flights table.
    """
    raw: list[dict] = json.loads(
        (_FIXTURES_DIR / filename).read_text(encoding="utf-8")
    )
    return pa.table(
        {
            "icao24": [r["icao24"] for r in raw],
            "callsign": [r["callsign"] for r in raw],
            "first_seen": [r["firstSeen"] for r in raw],
            "last_seen": [r["lastSeen"] for r in raw],
            "est_departure_airport": [r["estDepartureAirport"] for r in raw],
            "est_arrival_airport": [r["estArrivalAirport"] for r in raw],
        }
    )


# ---------------------------------------------------------------------------
# aws-chunked decoding
# ---------------------------------------------------------------------------


def _decode_aws_chunked(raw: bytes) -> bytes:
    """Decode an aws-chunked encoded byte stream into plain bytes.

    ``aiobotocore`` uploads objects with ``Content-Encoding: aws-chunked`` +
    ``Transfer-Encoding: chunked`` when request checksums are enabled.
    SeaweedFS stores the raw bytes verbatim, including the chunk-signature
    prefix line and trailing chunk terminator.  This function extracts the
    actual payload (lines that start with ``{`` for JSON, or binary data) by
    stripping the chunk header/trailer lines.

    The format is:
        <hex-len>;chunk-signature=<sig>\\r\\n
        <payload-bytes>\\r\\n
        0;chunk-signature=<sig>\\r\\n
        ...trailers...

    For binary payloads (Avro, Parquet) that do not start with ``{``, the
    function concatenates all non-header, non-trailer data segments.
    """
    # Fast path: if content doesn't look like aws-chunked, return as-is.
    if b";chunk-signature=" not in raw[:100]:
        return raw

    result_segments: list[bytes] = []
    i = 0
    while i < len(raw):
        # Find next CRLF which terminates the chunk header line.
        crlf_pos = raw.find(b"\r\n", i)
        if crlf_pos == -1:
            break
        header_line = raw[i:crlf_pos]
        i = crlf_pos + 2  # skip CRLF after header

        # Parse chunk size from header (format: "<hex>;chunk-signature=...")
        semicolon_pos = header_line.find(b";")
        size_hex = (
            header_line[:semicolon_pos] if semicolon_pos != -1 else header_line
        )
        try:
            chunk_size = int(size_hex, 16)
        except ValueError:
            break  # not a hex size — stop

        if chunk_size == 0:
            break  # final empty chunk

        # Extract chunk data (exactly chunk_size bytes).
        chunk_data = raw[i : i + chunk_size]
        result_segments.append(chunk_data)
        i += chunk_size + 2  # skip chunk data + CRLF after chunk

    return b"".join(result_segments)


# ---------------------------------------------------------------------------
# S3 mirror helpers
# ---------------------------------------------------------------------------


def _mirror_iceberg_table_to_canonical_path(
    s3: Any,
    uuid_prefix: str,
    bucket: str = "raw-flights",
) -> None:
    """Copy an Iceberg table from its UUID-suffixed path to the canonical path.

    DuckDB's ``iceberg_scan()`` reads from the fixed path
    ``s3://raw-flights/warehouse/flights/raw_flights`` as hardcoded in
    ``stg_flights.sql``.  Nessie's REST catalog always creates tables at
    ``<warehouse>/flights/raw_flights_<uuid>``.  This function bridges the gap
    by copying all Iceberg files to ``warehouse/flights/raw_flights/``, decoding
    ``aws-chunked`` encoding in the JSON/Avro metadata files and rewriting the
    ``"location"`` field so that ``allow_moved_paths = true`` resolves correctly.

    It also writes ``metadata/version-hint.text`` and ``metadata/v1.metadata.json``
    so that DuckDB can find the current snapshot without relying on glob-based
    version guessing (``unsafe_enable_version_guessing``).

    Args:
        s3: Boto3 S3 client.
        uuid_prefix: The S3 key prefix for the UUID-suffixed table directory
            (e.g. ``"warehouse/flights/raw_flights_abc123-.../"``).
        bucket: S3 bucket name.
    """
    canonical_prefix = _RAW_FLIGHTS_CANONICAL_S3_KEY + "/"
    old_location = ("s3://" + bucket + "/" + uuid_prefix.rstrip("/")).encode()
    new_location = _RAW_FLIGHTS_CANONICAL_LOCATION.encode()

    # Track the latest snapshot metadata file so we can create v1.metadata.json.
    latest_metadata_key: str | None = None
    latest_metadata_ts: int = -1

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=uuid_prefix):
        for obj in page.get("Contents", []):
            old_key: str = obj["Key"]
            relative = old_key[len(uuid_prefix):]
            new_key = canonical_prefix + relative

            raw: bytes = s3.get_object(Bucket=bucket, Key=old_key)["Body"].read()

            # Decode aws-chunked encoding present in pyiceberg/aiobotocore writes.
            decoded: bytes = _decode_aws_chunked(raw)

            # Rewrite "location" references in metadata JSON files.
            content: bytes = decoded.replace(old_location, new_location)

            content_type = (
                "application/json"
                if old_key.endswith(".json")
                else "application/octet-stream"
            )
            s3.put_object(Bucket=bucket, Key=new_key, Body=content, ContentType=content_type)

            # Track the latest metadata file by modification time.
            if old_key.endswith(".metadata.json") and "metadata/" in old_key:
                ts: int = obj["LastModified"].timestamp().__int__()
                if ts > latest_metadata_ts:
                    latest_metadata_ts = ts
                    latest_metadata_key = new_key

    if latest_metadata_key is None:
        raise RuntimeError(
            f"No metadata.json files found under {uuid_prefix!r}. "
            "Cannot create version-hint for DuckDB."
        )

    # Read the latest (canonical) metadata to use for v1.metadata.json.
    latest_content: bytes = s3.get_object(
        Bucket=bucket, Key=latest_metadata_key
    )["Body"].read()

    # Write version-hint.text + v1.metadata.json so DuckDB finds the snapshot
    # without glob-based version guessing.
    hint_key = canonical_prefix + "metadata/version-hint.text"
    v1_key = canonical_prefix + "metadata/v1.metadata.json"
    s3.put_object(Bucket=bucket, Key=hint_key, Body=b"1", ContentType="text/plain")
    s3.put_object(
        Bucket=bucket, Key=v1_key, Body=latest_content, ContentType="application/json"
    )


# ---------------------------------------------------------------------------
# Iceberg population
# ---------------------------------------------------------------------------


def _get_uuid_prefix(table_location: str, bucket: str = "raw-flights") -> str:
    """Extract the S3 key prefix from a ``s3://bucket/...`` table location URL."""
    prefix = table_location.removeprefix(f"s3://{bucket}/")
    return prefix.rstrip("/") + "/"


def _populate_raw_flights(endpoints: dict[str, str]) -> None:
    """Create and populate the flights.raw_flights Iceberg table, then mirror it.

    Creates the namespace and table if they do not already exist (idempotent
    with respect to a freshly started test stack).  Appends both departures
    and arrivals fixture records in a single batch, then mirrors the table to
    the canonical S3 path so DuckDB's iceberg_scan() can find it.
    """
    catalog = _build_catalog(endpoints)

    if not catalog.table_exists("flights.raw_flights"):
        catalog.create_namespace_if_not_exists("flights")
        catalog.create_table("flights.raw_flights", schema=_RAW_FLIGHTS_SCHEMA)

    departures = _load_fixture_as_arrow("departures_kjfk.json")
    arrivals = _load_fixture_as_arrow("arrivals_kjfk.json")
    combined = pa.concat_tables([departures, arrivals])

    table = catalog.load_table("flights.raw_flights")
    table.append(combined)

    # Re-load to get updated metadata location after append.
    table = catalog.load_table("flights.raw_flights")
    uuid_prefix = _get_uuid_prefix(table.location())

    s3 = _make_s3_client(endpoints)
    _mirror_iceberg_table_to_canonical_path(s3, uuid_prefix)


# ---------------------------------------------------------------------------
# dbt build helpers
# ---------------------------------------------------------------------------


def _build_dbt_env(
    endpoints: dict[str, str],
    duckdb_path: Path,
    raw_bucket: str = "raw-flights",
) -> dict[str, str]:
    """Build the environment mapping for the dbt build subprocess.

    Inherits the current process environment so that PATH, HOME, and other
    shell defaults are preserved; then overlays the test-specific variables.
    """
    return {
        **os.environ,
        "SEAWEEDFS_S3_ENDPOINT": endpoints["s3_endpoint"],
        "SEAWEEDFS_ACCESS_KEY": endpoints["s3_access_key"],
        "SEAWEEDFS_SECRET_KEY": endpoints["s3_secret_key"],
        "NESSIE_ENDPOINT": endpoints["nessie_uri"],
        "RAW_BUCKET": raw_bucket,
        "DBT_DUCKDB_PATH": str(duckdb_path),
    }


def _run_dbt_build(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run ``dbt build`` in *_TRANSFORMS_DIR* and return the result."""
    return subprocess.run(
        [
            "dbt",
            "build",
            "--profiles-dir",
            str(_TRANSFORMS_DIR),
            "--project-dir",
            str(_TRANSFORMS_DIR),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_TRANSFORMS_DIR),
    )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.integration
@skip_if_no_docker
@skip_if_no_dbt
def test_dbt_build_against_iceberg_fixture(
    infra_endpoints: dict[str, str],
    seaweedfs_init: None,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """Full fixture → Iceberg → dbt build → S3 parquet round-trip.

    Steps:
    1. Populate flights.raw_flights Iceberg table from KJFK fixture files,
       then mirror the UUID-suffixed table to the canonical S3 path so that
       DuckDB's iceberg_scan() in stg_flights.sql can find it.
    2. Run ``dbt build`` against pipeline/transforms/.
    3. Assert returncode == 0 (stdout/stderr surfaced on failure).
    4. Assert stg_flights view has rows in the DuckDB target file.
    5. Assert agg_daily_timeliness parquet was written to S3 and has rows
       when queried back via DuckDB with httpfs loaded.
    """
    # ---- 1. Populate Iceberg table and mirror to canonical path -------------
    _populate_raw_flights(infra_endpoints)

    # ---- 2. Run dbt build ---------------------------------------------------
    duckdb_path = tmp_path / "test_travel_pal.duckdb"
    env = _build_dbt_env(infra_endpoints, duckdb_path)
    result = _run_dbt_build(env)

    assert result.returncode == 0, (
        f"dbt build failed (returncode={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # ---- 3. Assert stg_flights view has rows in DuckDB ----------------------
    s3_endpoint_bare = (
        infra_endpoints["s3_endpoint"]
        .replace("http://", "")
        .replace("https://", "")
    )
    with duckdb.connect(str(duckdb_path), read_only=False) as con:
        # Extensions and S3 secret must be loaded before querying the views
        # that wrap iceberg_scan() calls.
        con.execute("INSTALL iceberg; LOAD iceberg;")
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute(
            f"""
            CREATE OR REPLACE SECRET travel_pal_s3 (
                TYPE s3,
                PROVIDER config,
                KEY_ID '{infra_endpoints["s3_access_key"]}',
                SECRET '{infra_endpoints["s3_secret_key"]}',
                ENDPOINT '{s3_endpoint_bare}',
                USE_SSL false,
                URL_STYLE path
            )
            """
        )

        stg_count: int = con.execute(
            "SELECT COUNT(*) FROM stg_flights"
        ).fetchone()[0]  # type: ignore[index]

    assert stg_count > 0, (
        f"Expected stg_flights to have rows but got {stg_count}. "
        "Check that the Iceberg table was populated and dbt build succeeded."
    )

    # ---- 4. Assert agg_daily_timeliness parquet on S3 has rows -------------
    raw_bucket = env.get("RAW_BUCKET", "raw-flights")
    parquet_s3_path = (
        f"s3://{raw_bucket}/warehouse/marts/agg_daily_timeliness.parquet"
    )

    with duckdb.connect(":memory:") as con:
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute(
            f"""
            CREATE OR REPLACE SECRET travel_pal_s3 (
                TYPE s3,
                PROVIDER config,
                KEY_ID '{infra_endpoints["s3_access_key"]}',
                SECRET '{infra_endpoints["s3_secret_key"]}',
                ENDPOINT '{s3_endpoint_bare}',
                USE_SSL false,
                URL_STYLE path
            )
            """
        )
        mart_count: int = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{parquet_s3_path}')"
        ).fetchone()[0]  # type: ignore[index]

    assert mart_count > 0, (
        f"Expected agg_daily_timeliness parquet at {parquet_s3_path} to have "
        f"rows but got {mart_count}.  Verify the dbt mart model ran and wrote "
        "its external parquet file to SeaweedFS S3."
    )
