import io
from functools import cached_property

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict


class SeaweedFSResource(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    @cached_property
    def _client(self):
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="us-east-1",
        )

    def upload_parquet(self, table: pa.Table, bucket: str, key: str) -> None:
        buf = io.BytesIO()
        pq.write_table(table, buf)
        buf.seek(0)
        self._client.put_object(Bucket=bucket, Key=key, Body=buf.read())

    def get_object(self, *, bucket: str, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=bucket, Key=key)
        except (
            self._client.exceptions.NoSuchKey,
            self._client.exceptions.NoSuchBucket,
        ) as exc:
            raise FileNotFoundError(f"s3://{bucket}/{key} not found") from exc
        return response["Body"].read()  # type: ignore[no-any-return]

    def put_object(self, *, bucket: str, key: str, body: bytes) -> None:
        # Auto-create the bucket on first write so callers don't need to
        # pre-provision SeaweedFS state. Idempotent: if the bucket already
        # exists (or is owned by us), the create call is a no-op.
        try:
            self._client.head_bucket(Bucket=bucket)
        except self._client.exceptions.ClientError:
            try:
                self._client.create_bucket(Bucket=bucket)
            except self._client.exceptions.BucketAlreadyOwnedByYou:
                pass
        self._client.put_object(Bucket=bucket, Key=key, Body=body)

    def get_public_url(self, bucket: str, key: str) -> str:
        return f"{self.endpoint}/{bucket}/{key}"
