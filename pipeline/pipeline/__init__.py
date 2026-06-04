import os

from dagster import Definitions, ResourceDefinition
from pydantic import ValidationError

from pipeline.assets.frontend_exports import frontend_exports
from pipeline.assets.raw_flights import raw_flights
from pipeline.assets.transformed_flights import transformed_flights
from pipeline.config import PipelineConfig
from pipeline.resources.nessie import NessieResource
from pipeline.resources.opensky import OpenSkyResource
from pipeline.resources.seaweedfs import SeaweedFSResource


def _make_resources() -> dict[str, ResourceDefinition]:
    cfg = PipelineConfig.from_env()
    # When OPENSKY_FIXTURE_DIR is set the resource reads JSON fixtures instead
    # of making live HTTP requests (token endpoint included).  This is the
    # mechanism used by CI E2E jobs.
    opensky = OpenSkyResource(
        client_id=cfg.opensky_client_id,
        client_secret=cfg.opensky_client_secret,
    )
    return {
        "pipeline_config": ResourceDefinition.hardcoded_resource(cfg),
        "opensky": ResourceDefinition.hardcoded_resource(opensky),
        "seaweedfs": ResourceDefinition.hardcoded_resource(
            SeaweedFSResource(
                endpoint=cfg.seaweedfs_endpoint,
                access_key=cfg.seaweedfs_access_key,
                secret_key=cfg.seaweedfs_secret_key,
            )
        ),
        "nessie": ResourceDefinition.hardcoded_resource(
            NessieResource(
                endpoint=cfg.nessie_endpoint,
                s3_endpoint=cfg.seaweedfs_endpoint,
                s3_access_key=cfg.seaweedfs_access_key,
                s3_secret_key=cfg.seaweedfs_secret_key,
            )
        ),
    }


def _resources_or_empty() -> dict[str, ResourceDefinition]:
    try:
        return _make_resources()
    except (KeyError, ValidationError):
        if os.environ.get("DAGSTER_ENV") == "prod":
            raise
        return {}


defs = Definitions(
    assets=[raw_flights, transformed_flights, frontend_exports],
    resources=_resources_or_empty(),
)
