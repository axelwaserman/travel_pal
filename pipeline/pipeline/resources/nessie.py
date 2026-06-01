from dataclasses import dataclass
from pyiceberg.catalog import Catalog, load_catalog


@dataclass
class NessieResource:
    endpoint: str

    def catalog(self) -> Catalog:
        return load_catalog(
            "nessie",
            **{
                "type": "rest",
                "uri": self.endpoint,
                "warehouse": "s3://raw-flights/warehouse",
            },
        )
