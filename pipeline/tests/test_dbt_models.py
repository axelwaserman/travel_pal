"""Regression tests for dbt model and profile file content.

These are file-content sanity checks — no runtime execution required.
They catch regressions like accidentally reverting to the unpopulated
DuckDB source reference or reintroducing a scheme prefix in s3_endpoint.
"""
import pathlib

import pytest
import yaml

TRANSFORMS_DIR = pathlib.Path(__file__).parents[1] / "transforms"
STAGING_DIR = TRANSFORMS_DIR / "models" / "staging"
MACROS_DIR = TRANSFORMS_DIR / "macros"


@pytest.mark.unit
def test_stg_flights_uses_iceberg_scan_with_s3_uri() -> None:
    """stg_flights.sql must read via iceberg_scan('s3://...'), not read_parquet or a dbt source.

    This ensures the Iceberg metadata layer (snapshots, manifests, partition specs)
    is honoured rather than bypassed by globbing raw parquet files.
    """
    sql = (STAGING_DIR / "stg_flights.sql").read_text()
    assert "iceberg_scan(" in sql, "stg_flights.sql must use iceberg_scan(...)"
    assert "read_parquet(" not in sql, (
        "stg_flights.sql must not fall back to read_parquet(...); use iceberg_scan instead"
    )
    assert "s3://" in sql, "iceberg_scan path must be an s3:// URI"
    assert "{{ source(" not in sql, (
        "stg_flights.sql must not reference an unpopulated dbt source"
    )


@pytest.mark.unit
def test_stg_flights_filters_empty_callsign() -> None:
    """callsign filter must use NULLIF(TRIM(...), '') so whitespace-only and empty are dropped."""
    sql = (STAGING_DIR / "stg_flights.sql").read_text()
    assert "NULLIF(TRIM(callsign), '')" in sql, (
        "stg_flights.sql must guard against empty/whitespace callsigns via NULLIF(TRIM(...), '')"
    )


@pytest.mark.unit
def test_profiles_s3_endpoint_default_has_no_scheme() -> None:
    """profiles.yml s3_endpoint default value must be bare host:port (no scheme).

    DuckDB rejects 'http://host:port' — only 'host:port' is accepted.
    The Jinja replace filters strip any injected scheme at render time.
    """
    profiles_text = (TRANSFORMS_DIR / "profiles.yml").read_text()
    # The default fallback value in env_var('...', 'localhost:8333') must not
    # contain a scheme prefix.
    assert "http://localhost" not in profiles_text, (
        "profiles.yml default for s3_endpoint must not contain 'http://localhost'; "
        "DuckDB rejects scheme prefixes"
    )
    assert "https://localhost" not in profiles_text, (
        "profiles.yml default for s3_endpoint must not contain 'https://localhost'"
    )
    # The replace filters that strip runtime env var values must be present.
    assert "replace('http://', '')" in profiles_text, (
        "profiles.yml must strip http:// scheme from s3_endpoint via Jinja replace"
    )


@pytest.mark.unit
def test_schema_yml_has_not_null_tests_on_icao24_and_departed_at() -> None:
    """models/staging/schema.yml must carry not_null tests on icao24 and departed_at."""
    schema_path = STAGING_DIR / "schema.yml"
    assert schema_path.exists(), (
        "models/staging/schema.yml must exist (replaces deleted sources.yml)"
    )
    schema = yaml.safe_load(schema_path.read_text())

    models = {m["name"]: m for m in schema.get("models", [])}
    assert "stg_flights" in models, "schema.yml must define the stg_flights model"

    columns = {c["name"]: c for c in models["stg_flights"].get("columns", [])}

    for col in ("icao24", "departed_at"):
        assert col in columns, f"schema.yml must declare column '{col}' on stg_flights"
        tests = columns[col].get("tests", [])
        assert "not_null" in tests, (
            f"schema.yml must have a not_null test on stg_flights.{col}"
        )


@pytest.mark.unit
def test_sources_yml_deleted() -> None:
    """sources.yml must not exist — it referenced an unpopulated DuckDB table."""
    sources_path = STAGING_DIR / "sources.yml"
    assert not sources_path.exists(), (
        "sources.yml must be deleted; stg_flights now reads parquet directly from S3"
    )


@pytest.mark.unit
def test_marts_use_external_parquet_materialization() -> None:
    """dbt_project.yml must configure marts as external parquet written to S3.

    This prevents regression to the old local-table materialization that
    coupled frontend_exports to a local DuckDB file.
    """
    dbt_project = yaml.safe_load(
        (TRANSFORMS_DIR / "dbt_project.yml").read_text()
    )

    marts_config = dbt_project["models"]["travel_pal"]["marts"]

    assert marts_config.get("+materialized") == "external", (
        "marts must use '+materialized: external' so dbt-duckdb writes parquet to S3"
    )
    assert marts_config.get("+format") == "parquet", (
        "marts must set '+format: parquet'"
    )
    location = marts_config.get("+location", "")
    assert "s3://" in location, (
        "marts '+location' must point to an s3:// URI"
    )
    assert "warehouse/marts/" in location, (
        "marts '+location' must write under warehouse/marts/"
    )


@pytest.mark.unit
def test_dbt_project_wires_setup_iceberg_on_run_start() -> None:
    """dbt_project.yml must call setup_iceberg() via on-run-start.

    This ensures DuckDB extensions and the S3 secret are configured before
    any model runs, so iceberg_scan() can resolve s3:// paths.
    """
    dbt_project = yaml.safe_load(
        (TRANSFORMS_DIR / "dbt_project.yml").read_text()
    )

    on_run_start = dbt_project.get("on-run-start", [])
    assert isinstance(on_run_start, list) and len(on_run_start) > 0, (
        "dbt_project.yml must declare at least one on-run-start hook"
    )
    joined = " ".join(on_run_start)
    assert "setup_iceberg" in joined, (
        "on-run-start must invoke the setup_iceberg() macro"
    )


@pytest.mark.unit
def test_setup_iceberg_macro_installs_extensions_and_creates_secret() -> None:
    """macros/setup_iceberg.sql must install iceberg + httpfs and create an S3 secret.

    These are the prerequisites for iceberg_scan() to resolve s3:// URIs
    against a custom SeaweedFS endpoint.
    """
    macro_path = MACROS_DIR / "setup_iceberg.sql"
    assert macro_path.exists(), "macros/setup_iceberg.sql must exist"

    text = macro_path.read_text()

    assert "INSTALL iceberg" in text, "macro must INSTALL iceberg extension"
    assert "LOAD iceberg" in text, "macro must LOAD iceberg extension"
    assert "INSTALL httpfs" in text, "macro must INSTALL httpfs extension"
    assert "LOAD httpfs" in text, "macro must LOAD httpfs extension"
    assert "CREATE OR REPLACE SECRET" in text, (
        "macro must create an S3 secret for iceberg_scan to resolve s3:// URIs"
    )
    assert "SEAWEEDFS_ACCESS_KEY" in text, (
        "macro must read S3 key from SEAWEEDFS_ACCESS_KEY env var"
    )
    assert "SEAWEEDFS_SECRET_KEY" in text, (
        "macro must read S3 secret from SEAWEEDFS_SECRET_KEY env var"
    )
    assert "SEAWEEDFS_S3_ENDPOINT" in text, (
        "macro must read S3 endpoint from SEAWEEDFS_S3_ENDPOINT env var"
    )
