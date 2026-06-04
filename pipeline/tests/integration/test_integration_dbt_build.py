"""Integration test: Iceberg fixture -> dbt build -> S3 parquet marts.

Exercises the full dbt path against the live Nessie + SeaweedFS stack:
    1. Populate ``flights.raw_flights`` via PyIceberg's RestCatalog.
    2. Run ``dbt build`` against ``pipeline/transforms/`` with a tmp-scoped
       DuckDB target file so repeated runs do not share state.
    3. Assert returncode == 0 and that both mart parquets exist on S3 and
       have at least one row when read back via DuckDB httpfs.

Marked ``@pytest.mark.integration``. Skipped when Docker is not reachable.

Depends on two production fixes already on the branch:
    - SeaweedFS 4.31 (commit 959ec5e) — fixes aws-chunked verbatim storage.
    - stg_flights via Nessie ATTACH (commit 9599d1a) — removes the
      hardcoded UUID-less table path that previously required mirroring.
"""
import os
import subprocess
import uuid
from pathlib import Path

import duckdb
import pyarrow as pa
import pytest
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.exceptions import (
    NamespaceAlreadyExistsError,
    NoSuchNamespaceError,
    NoSuchTableError,
)
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType

from tests.integration._docker import DOCKER_AVAILABLE

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).parent.parent.parent.parent  # …/travel_pal
_TRANSFORMS_DIR: Path = _REPO_ROOT / "pipeline" / "transforms"

# stg_flights.sql reads from "nessie.flights.raw_flights" via the Nessie REST
# ATTACH; the namespace and table names are therefore fixed by the dbt model.
# Per-run isolation is provided by tmp_path-scoped DuckDB and by dropping the
# table+namespace before recreating them.
_NAMESPACE: str = "flights"
_TABLE_NAME: str = "raw_flights"
_TABLE_ID: str = f"{_NAMESPACE}.{_TABLE_NAME}"

# Mart output keys mirror the +location config in agg_*_timeliness.sql.
_RAW_BUCKET: str = "raw-flights"
_MART_KEYS: tuple[str, ...] = (
    "warehouse/marts/agg_daily_timeliness.parquet",
    "warehouse/marts/agg_route_timeliness.parquet",
)

# Mirrors production raw_flights schema (pipeline/assets/raw_flights.py).
_SCHEMA: Schema = Schema(
    NestedField(1, "icao24", StringType(), required=False),
    NestedField(2, "callsign", StringType(), required=False),
    NestedField(3, "first_seen", LongType(), required=False),
    NestedField(4, "last_seen", LongType(), required=False),
    NestedField(5, "est_departure_airport", StringType(), required=False),
    NestedField(6, "est_arrival_airport", StringType(), required=False),
)

# Two surviving rows + one empty-callsign row that exercises the NULLIF guard
# in stg_flights.sql. The two surviving rows fly different dates so the daily
# mart receives more than one row, and share a route so the route mart groups.
_SAMPLE_ROWS: pa.Table = pa.table(
    {
        "icao24": ["a1b2c3", "aabbcc", "deadbe"],
        "callsign": ["AA100", "UA200", "   "],  # whitespace-only -> NULLIF
        "first_seen": [1704110400, 1704196800, 1704110400],
        "last_seen": [1704117600, 1704204000, 1704117600],
        "est_departure_airport": ["KJFK", "KJFK", "KJFK"],
        "est_arrival_airport": ["KLAX", "KLAX", "KLAX"],
    }
)

_SKIP_REASON = "Docker daemon is not reachable — skipping integration tests."
skip_if_no_docker = pytest.mark.skipif(not DOCKER_AVAILABLE, reason=_SKIP_REASON)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_catalog(endpoints: dict[str, str]) -> RestCatalog:
    """Build a RestCatalog pointing at the live Nessie + SeaweedFS stack."""
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


def _reset_namespace(catalog: RestCatalog) -> None:
    """Drop ``flights.raw_flights`` and the ``flights`` namespace if present.

    Ensures the test starts from a clean catalog state regardless of prior
    runs that may have left tables behind. Idempotent.
    """
    try:
        catalog.drop_table(_TABLE_ID)
    except NoSuchTableError:
        pass
    try:
        catalog.drop_namespace(_NAMESPACE)
    except NoSuchNamespaceError:
        pass


def _build_dbt_env(endpoints: dict[str, str], duckdb_path: Path) -> dict[str, str]:
    """Compose the env mapping passed to ``dbt build``.

    Inherits the parent process env (PATH, HOME, etc.) and overlays only the
    variables that ``profiles.yml`` and ``setup_iceberg.sql`` consume.
    """
    return {
        **os.environ,
        "SEAWEEDFS_S3_ENDPOINT": endpoints["s3_endpoint"],
        "SEAWEEDFS_ACCESS_KEY": endpoints["s3_access_key"],
        "SEAWEEDFS_SECRET_KEY": endpoints["s3_secret_key"],
        "NESSIE_ENDPOINT": endpoints["nessie_uri"],
        "NESSIE_WAREHOUSE": endpoints["warehouse"],
        "DBT_DUCKDB_PATH": str(duckdb_path),
        "RAW_BUCKET": _RAW_BUCKET,
    }


def _configure_duckdb_for_s3(con: duckdb.DuckDBPyConnection, endpoints: dict[str, str]) -> None:
    """Install httpfs + create an S3 secret for SeaweedFS reads.

    Mirrors the secret form used by ``macros/setup_iceberg.sql`` so the read
    path here behaves the same way dbt does on the production setup.
    """
    endpoint_host = (
        endpoints["s3_endpoint"].replace("http://", "").replace("https://", "")
    )
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(
        f"""
        CREATE OR REPLACE SECRET travel_pal_s3 (
            TYPE s3,
            PROVIDER config,
            KEY_ID '{endpoints["s3_access_key"]}',
            SECRET '{endpoints["s3_secret_key"]}',
            ENDPOINT '{endpoint_host}',
            USE_SSL false,
            URL_STYLE path,
            REGION 'us-east-1'
        );
        """
    )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.integration
@skip_if_no_docker
def test_dbt_build_against_iceberg_fixture(
    infra_endpoints: dict[str, str],
    seaweedfs_init: None,  # noqa: ARG001 — fixture side-effect (bucket init).
    tmp_path: Path,
) -> None:
    """End-to-end dbt build over Nessie-cataloged Iceberg + SeaweedFS S3."""
    catalog = _make_catalog(infra_endpoints)

    # 1. Reset and populate the canonical flights.raw_flights table.
    _reset_namespace(catalog)
    try:
        catalog.create_namespace(_NAMESPACE)
    except NamespaceAlreadyExistsError:
        # Concurrent run created it between our drop and create — fine.
        pass
    table = catalog.create_table(_TABLE_ID, schema=_SCHEMA)
    table.append(_SAMPLE_ROWS)

    # 2. Run dbt build with a tmp-scoped DuckDB so runs don't share state.
    #    The uuid suffix makes the path unique even if tmp_path is reused.
    duckdb_path = tmp_path / f"travel_pal_{uuid.uuid4().hex[:8]}.duckdb"
    env = _build_dbt_env(infra_endpoints, duckdb_path)
    result = subprocess.run(
        ["dbt", "build", "--project-dir", str(_TRANSFORMS_DIR),
         "--profiles-dir", str(_TRANSFORMS_DIR)],
        cwd=str(_TRANSFORMS_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"dbt build failed (exit={result.returncode})\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # 3. Verify each mart parquet exists on S3 and has at least one row.
    con = duckdb.connect(":memory:")
    try:
        _configure_duckdb_for_s3(con, infra_endpoints)
        for key in _MART_KEYS:
            uri = f"s3://{_RAW_BUCKET}/{key}"
            row = con.execute(
                f"SELECT COUNT(*) FROM read_parquet('{uri}')"
            ).fetchone()
            assert row is not None, f"COUNT(*) returned no row for {uri}"
            assert row[0] > 0, f"Mart parquet {uri} has zero rows"
    finally:
        con.close()
