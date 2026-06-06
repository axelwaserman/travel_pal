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
MARTS_DIR = TRANSFORMS_DIR / "models" / "marts"
MACROS_DIR = TRANSFORMS_DIR / "macros"


@pytest.mark.unit
def test_stg_flights_reads_via_attached_nessie_catalog() -> None:
    """stg_flights.sql must read via the Nessie REST catalog (ATTACHed in the
    setup_iceberg macro), not iceberg_scan() with a hardcoded S3 path.

    Nessie appends a UUID to the table location on every create, so the
    catalog is the only authority on the current path. Hardcoding it is a
    bug: writes from PyIceberg + reads from a hardcoded path will diverge.
    """
    sql = (STAGING_DIR / "stg_flights.sql").read_text()
    assert "FROM nessie." in sql, (
        "stg_flights.sql must read FROM the ATTACHed nessie catalog "
        "(e.g. FROM nessie.flights.raw_flights)"
    )
    assert "iceberg_scan(" not in sql, (
        "stg_flights.sql must not call iceberg_scan() with a hardcoded path; "
        "use the Nessie catalog ATTACH instead"
    )
    assert "read_parquet(" not in sql, "stg_flights.sql must not fall back to read_parquet(...)"
    assert "{{ source(" not in sql, "stg_flights.sql must not reference an unpopulated dbt source"


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
        assert "not_null" in tests, f"schema.yml must have a not_null test on stg_flights.{col}"


@pytest.mark.unit
def test_sources_yml_deleted() -> None:
    """sources.yml must not exist — it referenced an unpopulated DuckDB table."""
    sources_path = STAGING_DIR / "sources.yml"
    assert not sources_path.exists(), (
        "sources.yml must be deleted; stg_flights now reads via iceberg_scan, not a dbt source ref"
    )


@pytest.mark.unit
def test_marts_use_external_parquet_materialization() -> None:
    """dbt_project.yml must configure marts as external parquet, and each mart
    model must declare its own +location pointing to S3.

    Per-model location is required because dbt_project.yml does not have
    `this` available at parse time; `{{ this.name }}` only resolves inside
    a model's config() block.
    """
    dbt_project = yaml.safe_load((TRANSFORMS_DIR / "dbt_project.yml").read_text())

    marts_config = dbt_project["models"]["travel_pal"]["marts"]

    assert marts_config.get("+materialized") == "external", (
        "marts must use '+materialized: external' so dbt-duckdb writes parquet to S3"
    )
    assert marts_config.get("+format") == "parquet", "marts must set '+format: parquet'"

    marts_dir = TRANSFORMS_DIR / "models" / "marts"
    for mart in marts_dir.glob("*.sql"):
        text = mart.read_text()
        assert "config(" in text and "location=" in text, (
            f"{mart.name} must declare its own location via {{{{ config(location=...) }}}}; "
            "dbt_project.yml cannot reference `this` at parse time"
        )
        assert "s3://" in text and "warehouse/marts/" in text, (
            f"{mart.name} location must be an s3:// URI under warehouse/marts/"
        )


@pytest.mark.unit
@pytest.mark.parametrize("mart", ["agg_daily_timeliness", "agg_route_timeliness"])
def test_marts_coalesce_stddev_to_zero(mart: str) -> None:
    """Aggregation marts must wrap STDDEV(delay_minutes) in COALESCE(..., 0).

    STDDEV over a single-row group returns NULL in DuckDB; the frontend
    treats those as missing data when they are really "not enough samples
    to compute volatility, but volatility is zero". Coalescing to 0 in the
    mart removes the null path entirely and keeps the column non-nullable.
    """
    sql = (MARTS_DIR / f"{mart}.sql").read_text()
    assert "COALESCE(STDDEV(delay_minutes), 0)" in sql, (
        f"{mart}.sql must wrap STDDEV(delay_minutes) in COALESCE(..., 0) — "
        "single-row groups produce NULL otherwise"
    )


@pytest.mark.unit
def test_dbt_project_wires_setup_iceberg_on_run_start() -> None:
    """dbt_project.yml must call setup_iceberg() via on-run-start.

    This ensures DuckDB extensions and the S3 secret are configured before
    any model runs, so iceberg_scan() can resolve s3:// paths.
    """
    dbt_project = yaml.safe_load((TRANSFORMS_DIR / "dbt_project.yml").read_text())

    on_run_start = dbt_project.get("on-run-start", [])
    assert isinstance(on_run_start, list) and len(on_run_start) > 0, (
        "dbt_project.yml must declare at least one on-run-start hook"
    )
    joined = " ".join(on_run_start)
    assert "setup_iceberg" in joined, "on-run-start must invoke the setup_iceberg() macro"


@pytest.mark.unit
def test_setup_iceberg_macro_installs_extensions_creates_secret_and_attaches_catalog() -> None:
    """macros/setup_iceberg.sql must install iceberg + httpfs, create an S3
    secret, and ATTACH the Nessie REST catalog with vended credentials disabled.

    Nessie does not vend access keys for self-hosted SeaweedFS, so DuckDB must
    fall back to the explicit S3 secret for object-store reads.
    """
    macro_path = MACROS_DIR / "setup_iceberg.sql"
    assert macro_path.exists(), "macros/setup_iceberg.sql must exist"

    text = macro_path.read_text()

    assert "INSTALL iceberg" in text, "macro must INSTALL iceberg extension"
    assert "LOAD iceberg" in text, "macro must LOAD iceberg extension"
    assert "INSTALL httpfs" in text, "macro must INSTALL httpfs extension"
    assert "LOAD httpfs" in text, "macro must LOAD httpfs extension"
    assert "CREATE OR REPLACE SECRET" in text, (
        "macro must create an S3 secret for object-store reads"
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
    assert 'replace("http://", "")' in text, (
        "macro ENDPOINT must strip http:// scheme via Jinja replace — "
        "DuckDB CREATE SECRET rejects scheme prefixes"
    )
    assert "ATTACH" in text and "TYPE iceberg" in text, (
        "macro must ATTACH the Nessie REST catalog via TYPE iceberg"
    )
    assert "NESSIE_ENDPOINT" in text, "macro must point ATTACH at NESSIE_ENDPOINT env var"
    assert "ACCESS_DELEGATION_MODE 'none'" in text, (
        "macro must disable vended credentials — Nessie does not return "
        "access keys for self-hosted SeaweedFS"
    )


@pytest.mark.unit
def test_dbt_project_configures_seeds() -> None:
    """dbt_project.yml must declare a seeds: block with quote_columns disabled.

    OurAirports + OpenFlights seeds carry numeric (lat/lon) columns; if
    +quote_columns were left at the dbt default of true, dbt-duckdb would
    materialise everything as VARCHAR and the staging joins would coerce
    awkwardly.
    """
    dbt_project = yaml.safe_load((TRANSFORMS_DIR / "dbt_project.yml").read_text())
    seeds = dbt_project.get("seeds", {})
    travel_pal_seeds = seeds.get("travel_pal", {})
    assert travel_pal_seeds.get("+quote_columns") is False, (
        "seeds.travel_pal.+quote_columns must be false so DuckDB infers "
        "numeric types from dim_airport.lat/lon"
    )


@pytest.mark.unit
def test_dbt_seeds_present() -> None:
    """The dim_airport and dim_carrier seeds must exist with ICAO as the first column."""
    seeds_dir = TRANSFORMS_DIR / "seeds"
    for seed in ("dim_airport.csv", "dim_carrier.csv"):
        path = seeds_dir / seed
        assert path.exists(), f"transforms/seeds/{seed} must exist"
        first_line = path.read_text().splitlines()[0]
        assert first_line.split(",")[0] == "icao", (
            f"{seed} first column must be 'icao' (canonical PK across the warehouse)"
        )
