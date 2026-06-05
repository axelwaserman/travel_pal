from functools import cached_property

from pydantic import BaseModel, ConfigDict
from pyiceberg.catalog import Catalog, load_catalog


class NessieResource(BaseModel):
    """Iceberg catalog resource backed by Nessie's Iceberg REST Catalog.

    Requires Nessie >= 0.91 with the iceberg-catalog module enabled.  The
    ``endpoint`` should point at the Iceberg REST root (e.g.
    ``http://nessie:19120/iceberg/``), not the legacy ``/api/v1`` path.

    The ``warehouse`` is a *named* warehouse declared server-side via
    ``NESSIE_CATALOG_WAREHOUSES_<NAME>_LOCATION``.  S3 credentials and
    endpoint are passed to PyIceberg so it can read/write data files on
    SeaweedFS directly.
    """

    endpoint: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    warehouse: str = "warehouse"
    s3_region: str = "us-east-1"

    model_config = ConfigDict(frozen=True)

    @cached_property
    def catalog(self) -> Catalog:
        return load_catalog(
            "nessie",
            **{
                "type": "rest",
                "uri": self.endpoint,
                "warehouse": self.warehouse,
                "s3.endpoint": self.s3_endpoint,
                "s3.access-key-id": self.s3_access_key,
                "s3.secret-access-key": self.s3_secret_key,
                "s3.path-style-access": "true",
                "s3.region": self.s3_region,
            },
        )
