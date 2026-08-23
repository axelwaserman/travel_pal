FROM python:3.13-slim

WORKDIR /opt/dagster/app

COPY pyproject.toml .
RUN pip install -e .

# Pre-install DuckDB extensions at build time so the container has no
# outbound extension download at runtime (extensions.duckdb.org unreachable).
RUN python -c "import duckdb; c = duckdb.connect(); c.install_extension('httpfs'); c.install_extension('iceberg'); c.close()"

COPY pipeline/ pipeline/
COPY transforms/ transforms/
