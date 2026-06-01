from dataclasses import dataclass
from functools import cached_property
from pyiceberg.catalog import Catalog, load_catalog


@dataclass
class NessieResource:
    endpoint: str

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
