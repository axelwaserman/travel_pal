import os
from dagster import Definitions, ResourceDefinition
from pipeline.assets.raw_flights import raw_flights
from pipeline.assets.transformed_flights import transformed_flights
from pipeline.assets.frontend_exports import frontend_exports
from pipeline.config import PipelineConfig
from pydantic import ValidationError
from pipeline.resources.opensky import OpenSkyAdapter
from pipeline.resources.seaweedfs import SeaweedFSResource
from pipeline.resources.nessie import NessieResource


def _make_resources() -> dict[str, ResourceDefinition]:
    cfg = PipelineConfig.from_env()
    # When OPENSKY_FIXTURE_DIR is set the adapter reads JSON fixtures instead
    # of making live HTTP requests.  This is the mechanism used by CI E2E jobs.
    opensky = OpenSkyAdapter(username=cfg.opensky_username, password=cfg.opensky_password)
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
            NessieResource(endpoint=cfg.nessie_endpoint)
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
