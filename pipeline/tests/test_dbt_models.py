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


@pytest.mark.unit
def test_stg_bts_on_time_inner_joins_dim_airport_and_dim_carrier() -> None:
    """stg_bts_on_time.sql must inner-join dim_airport (origin + dest) and dim_carrier."""
    sql = (STAGING_DIR / "stg_bts_on_time.sql").read_text()
    assert "INNER JOIN {{ ref('dim_airport') }}" in sql
    assert sql.count("INNER JOIN {{ ref('dim_airport') }}") == 2, (
        "stg_bts_on_time must INNER JOIN dim_airport twice (origin + dest)"
    )
    assert "INNER JOIN {{ ref('dim_carrier') }}" in sql


@pytest.mark.unit
def test_stg_bts_on_time_filters_empty_iata_codes() -> None:
    """stg_bts_on_time must filter rows with empty IATA codes via NULLIF."""
    sql = (STAGING_DIR / "stg_bts_on_time.sql").read_text()
    for col in ("origin_iata", "destination_iata", "carrier_iata"):
        assert f"NULLIF(b.{col}, '') IS NOT NULL" in sql, (
            f"stg_bts_on_time must filter empty {col} via NULLIF"
        )


@pytest.mark.unit
def test_stg_bts_on_time_carries_carrier_name_through() -> None:
    """stg_bts_on_time aliases dim_carrier.name as carrier_name so marts don't re-join."""
    sql = (STAGING_DIR / "stg_bts_on_time.sql").read_text()
    assert "c.name" in sql and "AS carrier_name" in sql


@pytest.mark.unit
def test_stg_bts_coverage_test_exists() -> None:
    """A dbt singular test guarding the IATA→ICAO mapping coverage must exist."""
    sql = (TRANSFORMS_DIR / "tests" / "stg_bts_coverage.sql").read_text()
    assert "stg_bts_on_time" in sql
    assert "0.99" in sql
    assert "severity='warn'" in sql


@pytest.mark.unit
@pytest.mark.parametrize("mart", ["agg_carrier_cancellations", "agg_route_cancellations"])
def test_cancellation_marts_use_external_parquet_with_correct_location(mart: str) -> None:
    """Each cancellation mart must declare an s3:// location for external parquet."""
    sql = (MARTS_DIR / f"{mart}.sql").read_text()
    assert "config(" in sql and "location=" in sql
    assert "s3://" in sql and "warehouse/marts/" in sql
    assert "this.name" in sql, f"{mart}.sql must reference its own name via {{{{ this.name }}}}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "mart,required",
    [
        (
            "agg_carrier_cancellations",
            (
                "origin_icao",
                "carrier_icao",
                "carrier_name",
                "total_scheduled",
                "cancelled",
                "cancellation_rate",
                "period_start",
                "period_end",
            ),
        ),
        (
            "agg_route_cancellations",
            (
                "origin_icao",
                "destination_icao",
                "total_scheduled",
                "cancelled",
                "cancellation_rate",
                "period_start",
                "period_end",
            ),
        ),
    ],
)
def test_cancellation_marts_have_required_columns(mart: str, required: tuple[str, ...]) -> None:
    sql = (MARTS_DIR / f"{mart}.sql").read_text()
    for col in required:
        assert col in sql, f"{mart}.sql missing required column {col}"


@pytest.mark.unit
@pytest.mark.parametrize("mart", ["agg_carrier_cancellations", "agg_route_cancellations"])
def test_cancellation_rate_uses_nullif_count_pattern(mart: str) -> None:
    """NULLIF(COUNT(*), 0) guards against empty-group division."""
    sql = (MARTS_DIR / f"{mart}.sql").read_text()
    assert "NULLIF(COUNT(*), 0)" in sql, (
        f"{mart}.sql must use NULLIF(COUNT(*), 0) for the cancellation_rate denom"
    )


# ---------------------------------------------------------------------------
# P2.3 new marts: agg_carrier_route_cancellations + agg_route_cancellation_reasons
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_agg_carrier_route_cancellations_exists_with_correct_location() -> None:
    """agg_carrier_route_cancellations.sql must exist with s3:// location and this.name."""
    sql = (MARTS_DIR / "agg_carrier_route_cancellations.sql").read_text()
    assert "config(" in sql and "location=" in sql
    assert "s3://" in sql and "warehouse/marts/" in sql
    assert "this.name" in sql, (
        "agg_carrier_route_cancellations.sql must reference its own name via {{ this.name }}"
    )


@pytest.mark.unit
def test_agg_carrier_route_cancellations_has_required_columns() -> None:
    """agg_carrier_route_cancellations must expose all P2.3 required columns."""
    sql = (MARTS_DIR / "agg_carrier_route_cancellations.sql").read_text()
    for col in (
        "origin_icao",
        "destination_icao",
        "carrier_icao",
        "carrier_name",
        "total_scheduled",
        "cancelled",
        "cancellation_rate",
        "period_start",
        "period_end",
    ):
        assert col in sql, f"agg_carrier_route_cancellations.sql missing required column {col}"


@pytest.mark.unit
def test_agg_carrier_route_cancellations_groups_by_three_keys() -> None:
    """Must GROUP BY origin_icao, destination_icao, carrier_icao."""
    sql = (MARTS_DIR / "agg_carrier_route_cancellations.sql").read_text()
    assert "GROUP BY origin_icao, destination_icao, carrier_icao" in sql


@pytest.mark.unit
def test_agg_carrier_route_cancellations_rate_uses_nullif_count_pattern() -> None:
    """NULLIF(COUNT(*), 0) guards against empty-group division."""
    sql = (MARTS_DIR / "agg_carrier_route_cancellations.sql").read_text()
    assert "NULLIF(COUNT(*), 0)" in sql, (
        "agg_carrier_route_cancellations.sql must use NULLIF(COUNT(*), 0)"
    )


@pytest.mark.unit
def test_agg_route_cancellation_reasons_exists_with_correct_location() -> None:
    """agg_route_cancellation_reasons.sql must exist with s3:// location and this.name."""
    sql = (MARTS_DIR / "agg_route_cancellation_reasons.sql").read_text()
    assert "config(" in sql and "location=" in sql
    assert "s3://" in sql and "warehouse/marts/" in sql
    assert "this.name" in sql, (
        "agg_route_cancellation_reasons.sql must reference its own name via {{ this.name }}"
    )


@pytest.mark.unit
def test_agg_route_cancellation_reasons_has_required_columns() -> None:
    """agg_route_cancellation_reasons must expose all P2.3 required columns."""
    sql = (MARTS_DIR / "agg_route_cancellation_reasons.sql").read_text()
    for col in (
        "origin_icao",
        "destination_icao",
        "reason",
        "cancelled_count",
        "reason_share",
    ):
        assert col in sql, f"agg_route_cancellation_reasons.sql missing required column {col}"


@pytest.mark.unit
def test_agg_route_cancellation_reasons_maps_cancellation_codes() -> None:
    """All five BTS cancellation_code labels must appear in the CASE expression."""
    sql = (MARTS_DIR / "agg_route_cancellation_reasons.sql").read_text()
    for label in ("Air Carrier", "Weather", "National Air System", "Security", "Other / Unknown"):
        assert label in sql, (
            f"agg_route_cancellation_reasons.sql missing cancellation reason label '{label}'"
        )


@pytest.mark.unit
def test_agg_route_cancellation_reasons_filters_uncancelled_rows() -> None:
    """Reason mart must filter to cancelled = TRUE rows only."""
    sql = (MARTS_DIR / "agg_route_cancellation_reasons.sql").read_text()
    assert "cancelled = TRUE" in sql, (
        "agg_route_cancellation_reasons.sql must filter WHERE cancelled = TRUE"
    )


@pytest.mark.unit
def test_agg_route_cancellation_reasons_reason_share_uses_window_sum() -> None:
    """reason_share must be computed as COUNT(*) / window SUM(COUNT(*)) OVER partition."""
    sql = (MARTS_DIR / "agg_route_cancellation_reasons.sql").read_text()
    assert "SUM(COUNT(*)) OVER" in sql, (
        "agg_route_cancellation_reasons.sql must use a window SUM for reason_share"
    )


@pytest.mark.unit
def test_marts_schema_yml_covers_new_marts() -> None:
    """pipeline/transforms/models/marts/schema.yml must declare both P2.3 new marts."""
    schema_path = MARTS_DIR / "schema.yml"
    assert schema_path.exists(), "pipeline/transforms/models/marts/schema.yml must exist"
    schema = yaml.safe_load(schema_path.read_text())
    model_names = {m["name"] for m in schema.get("models", [])}
    assert "agg_carrier_route_cancellations" in model_names, (
        "schema.yml must declare agg_carrier_route_cancellations"
    )
    assert "agg_route_cancellation_reasons" in model_names, (
        "schema.yml must declare agg_route_cancellation_reasons"
    )


@pytest.mark.unit
def test_schema_yml_carrier_route_has_not_null_on_grain_columns() -> None:
    """agg_carrier_route_cancellations grain columns must have not_null tests."""
    schema_path = MARTS_DIR / "schema.yml"
    assert schema_path.exists(), "pipeline/transforms/models/marts/schema.yml must exist"
    schema = yaml.safe_load(schema_path.read_text())
    models = {m["name"]: m for m in schema.get("models", [])}
    assert "agg_carrier_route_cancellations" in models
    cols = {c["name"]: c for c in models["agg_carrier_route_cancellations"].get("columns", [])}
    for grain_col in (
        "origin_icao",
        "destination_icao",
        "carrier_icao",
        "total_scheduled",
        "cancelled",
    ):
        assert grain_col in cols, (
            f"schema.yml agg_carrier_route_cancellations must declare column '{grain_col}'"
        )
        tests = cols[grain_col].get("tests", [])
        assert "not_null" in tests, (
            f"schema.yml must have a not_null test on agg_carrier_route_cancellations.{grain_col}"
        )


@pytest.mark.unit
def test_schema_yml_route_reasons_has_not_null_and_accepted_values() -> None:
    """agg_route_cancellation_reasons reason column must have not_null + accepted_values."""
    schema_path = MARTS_DIR / "schema.yml"
    assert schema_path.exists(), "pipeline/transforms/models/marts/schema.yml must exist"
    schema = yaml.safe_load(schema_path.read_text())
    models = {m["name"]: m for m in schema.get("models", [])}
    assert "agg_route_cancellation_reasons" in models
    cols = {c["name"]: c for c in models["agg_route_cancellation_reasons"].get("columns", [])}
    for grain_col in ("origin_icao", "destination_icao", "reason", "cancelled_count"):
        assert grain_col in cols, (
            f"schema.yml agg_route_cancellation_reasons must declare column '{grain_col}'"
        )
        tests = cols[grain_col].get("tests", [])
        assert "not_null" in tests, (
            f"schema.yml must have a not_null test on agg_route_cancellation_reasons.{grain_col}"
        )
    # reason must also have accepted_values
    reason_tests = cols["reason"].get("tests", [])
    has_accepted_values = any(isinstance(t, dict) and "accepted_values" in t for t in reason_tests)
    assert has_accepted_values, (
        "schema.yml agg_route_cancellation_reasons.reason must have an accepted_values test"
    )
