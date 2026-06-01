FROM python:3.12-slim

WORKDIR /opt/dagster/app

COPY pyproject.toml .
RUN pip install -e ".[dev]"

COPY pipeline/ pipeline/
COPY transforms/ transforms/
