from dagster import Definitions
from pipeline.assets.raw_flights import raw_flights
from pipeline.assets.transformed_flights import transformed_flights
from pipeline.assets.frontend_exports import frontend_exports

defs = Definitions(
    assets=[raw_flights, transformed_flights, frontend_exports],
)
