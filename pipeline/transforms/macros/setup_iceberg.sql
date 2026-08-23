{% macro setup_iceberg() %}
    {#
        Installs DuckDB extensions and ATTACHes the Nessie Iceberg REST catalog so
        models can read Iceberg tables by catalog identifier rather than addressing
        S3 paths directly.  This avoids the UUID-suffixed table-location coupling
        that would otherwise leak into staging SQL: Nessie always appends a UUID to
        the warehouse path (`<warehouse>/<ns>/<table>_<uuid>/`), and the catalog is
        the only authority on the current location.

        S3 access for data files goes through the `travel_pal_s3` secret because
        Nessie's vended credentials (`X-Iceberg-Access-Delegation: vended-credentials`)
        do not include access keys for self-hosted SeaweedFS.  We pin
        `ACCESS_DELEGATION_MODE 'none'` so DuckDB skips the vended-creds path and
        falls back to the matching S3 secret for object-store reads.

        `AUTHORIZATION_TYPE 'none'` matches Nessie's default unauthenticated REST
        endpoint in the dev/test stack.  Production deployments that put auth in
        front of Nessie would change this and add an ICEBERG SECRET with a token.
    #}
    CREATE OR REPLACE SECRET travel_pal_s3 (
        TYPE s3,
        PROVIDER config,
        KEY_ID '{{ env_var("SEAWEEDFS_ACCESS_KEY", "admin") }}',
        SECRET '{{ env_var("SEAWEEDFS_SECRET_KEY", "admin") }}',
        ENDPOINT '{{ env_var("SEAWEEDFS_S3_ENDPOINT", "localhost:8333") | replace("http://", "") | replace("https://", "") }}',
        USE_SSL false,
        URL_STYLE path,
        REGION 'us-east-1'
    );

    ATTACH '{{ env_var("NESSIE_WAREHOUSE", "warehouse") }}' AS nessie (
        TYPE iceberg,
        ENDPOINT '{{ env_var("NESSIE_ENDPOINT", "http://localhost:19120/iceberg/") }}',
        AUTHORIZATION_TYPE 'none',
        ACCESS_DELEGATION_MODE 'none'
    );
{% endmacro %}
