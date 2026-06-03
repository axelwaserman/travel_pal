from functools import cached_property

from pydantic import BaseModel, ConfigDict
from pyiceberg.catalog import Catalog, load_catalog


class NessieResource(BaseModel):
    endpoint: str

    model_config = ConfigDict(frozen=True)

    @cached_property
    def catalog(self) -> Catalog:
        return load_catalog(
            "nessie",
            **{
                "type": "rest",
                "uri": self.endpoint,
                "warehouse": "s3://raw-flights/warehouse",
            },
        )
