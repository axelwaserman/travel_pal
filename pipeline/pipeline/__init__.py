import os
from dagster import Definitions, ResourceDefinition
from pipeline.assets.raw_flights import raw_flights
from pipeline.assets.transformed_flights import transformed_flights
from pipeline.assets.frontend_exports import frontend_exports
from pipeline.config import PipelineConfig
from pipeline.resources.opensky import OpenSkyAdapter
from pipeline.resources.seaweedfs import SeaweedFSResource
from pipeline.resources.nessie import NessieResource


def _make_resources():
    cfg = PipelineConfig.from_env()
    return {
        "pipeline_config": ResourceDefinition.hardcoded_resource(cfg),
        "opensky": ResourceDefinition.hardcoded_resource(OpenSkyAdapter()),
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


def _resources_or_empty():
    try:
        return _make_resources()
    except KeyError:
        return {}


defs = Definitions(
    assets=[raw_flights, transformed_flights, frontend_exports],
    resources=_resources_or_empty(),
)
