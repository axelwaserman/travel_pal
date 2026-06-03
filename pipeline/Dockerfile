FROM python:3.13-slim

WORKDIR /opt/dagster/app

COPY pyproject.toml .
RUN pip install -e .

COPY pipeline/ pipeline/
COPY transforms/ transforms/
