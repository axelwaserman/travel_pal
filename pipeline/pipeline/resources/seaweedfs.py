import io
import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from dataclasses import dataclass
from functools import cached_property


@dataclass
class SeaweedFSResource:
    endpoint: str
    access_key: str
    secret_key: str

    @cached_property
    def _client(self):
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    def upload_parquet(self, table: pa.Table, bucket: str, key: str) -> None:
        buf = io.BytesIO()
        pq.write_table(table, buf)
        buf.seek(0)
        self._client.put_object(Bucket=bucket, Key=key, Body=buf.read())

    def get_public_url(self, bucket: str, key: str) -> str:
        return f"{self.endpoint}/{bucket}/{key}"
