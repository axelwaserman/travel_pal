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


@pytest.mark.unit
def test_stg_flights_uses_read_parquet_with_s3_uri() -> None:
    """stg_flights.sql must read from read_parquet('s3://...') not a dbt source."""
    sql = (STAGING_DIR / "stg_flights.sql").read_text()
    assert "read_parquet(" in sql, "stg_flights.sql must use read_parquet(...)"
    assert "s3://" in sql, "read_parquet path must be an s3:// URI"
    assert "{{ source(" not in sql, (
        "stg_flights.sql must not reference an unpopulated dbt source"
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
