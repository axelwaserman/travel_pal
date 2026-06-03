{% macro setup_iceberg() %}
    {#
        Installs and loads the DuckDB extensions required to read Iceberg tables
        from a custom S3-compatible endpoint (SeaweedFS).

        Run via on-run-start so that iceberg_scan() calls in models work regardless
        of whether the DuckDB binary ships extensions pre-bundled.

        S3 credentials are taken from the same env vars used by the Dagster pipeline
        so that the dbt run and the asset writes target the same bucket.

        Note: profiles.yml already installs/loads these extensions and configures S3
        via SET statements per cursor.  This macro is a belt-and-suspenders guarantee:
        it makes the intent explicit in SQL and ensures the secret is present when
        iceberg_scan() resolves S3 paths inside model queries.

        Nessie REST catalog support:
        DuckDB's iceberg extension (as of v1.x) does NOT expose a first-class
        REST catalog connector; it reads Iceberg metadata directly from object
        storage.  The raw_flights Iceberg table is managed by pyiceberg + Nessie,
        but dbt reads it by addressing the table root on S3 — Nessie is only needed
        for writes (the Dagster asset side).  Catalog registration via Nessie is
        deferred to a future task once DuckDB gains native REST catalog support.
    #}
    INSTALL iceberg;
    LOAD iceberg;
    INSTALL httpfs;
    LOAD httpfs;

    CREATE OR REPLACE SECRET travel_pal_s3 (
        TYPE s3,
        PROVIDER config,
        KEY_ID '{{ env_var("SEAWEEDFS_ACCESS_KEY", "admin") }}',
        SECRET '{{ env_var("SEAWEEDFS_SECRET_KEY", "admin") }}',
        ENDPOINT '{{ env_var("SEAWEEDFS_S3_ENDPOINT", "localhost:8333") | replace("http://", "") | replace("https://", "") }}',
        USE_SSL false,
        URL_STYLE path
    );
{% endmacro %}
