"""S3-API object storage adapter (boto3).

Works identically against MinIO locally and any S3-compatible production
store — the application never touches a cloud SDK's proprietary client
(Milestone 1's open-protocol principle).

Two boto3 clients exist on purpose:
- `_client` talks to storage over the service's own network path
  (head/delete/bucket ops);
- `_presign_client` only signs URLs, using the endpoint CLIENTS will reach
  (locally: the host-published MinIO port). SigV4 signatures cover the Host
  header, so the signing client must be configured with the exact endpoint
  the browser/SDK will hit or every signed URL would 403.
"""

from __future__ import annotations

import logging

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from catalog_service.application.errors import ObjectStorageError
from catalog_service.application.ports import ObjectStat, ObjectStoragePort, PresignedUpload

logger = logging.getLogger(__name__)

_MISSING_CODES = {"404", "NoSuchKey", "NotFound", "NoSuchBucket"}


class S3ObjectStorage(ObjectStoragePort):
    def __init__(
        self,
        endpoint_url: str,
        presign_endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        config = Config(signature_version="s3v4", s3={"addressing_style": "path"})

        def make_client(endpoint: str):
            return boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
                config=config,
            )

        self._client = make_client(endpoint_url)
        self._presign_client = (
            self._client
            if presign_endpoint_url == endpoint_url
            else make_client(presign_endpoint_url)
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            if _error_code(exc) not in _MISSING_CODES:
                raise ObjectStorageError("object storage unavailable") from exc
            self._client.create_bucket(Bucket=self._bucket)
            logger.info("created object storage bucket '%s'", self._bucket)

    def presign_upload(
        self, object_key: str, content_type: str, expires_in_seconds: int
    ) -> PresignedUpload:
        url = self._presign_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": object_key, "ContentType": content_type},
            ExpiresIn=expires_in_seconds,
        )
        return PresignedUpload(
            url=url,
            method="PUT",
            # Content-Type participates in the signature; the client must send
            # exactly this header or storage rejects the upload.
            headers={"Content-Type": content_type},
            expires_in_seconds=expires_in_seconds,
        )

    def presign_download(self, object_key: str, expires_in_seconds: int) -> str:
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": object_key},
            ExpiresIn=expires_in_seconds,
        )

    def stat_object(self, object_key: str) -> ObjectStat | None:
        try:
            head = self._client.head_object(Bucket=self._bucket, Key=object_key)
        except ClientError as exc:
            if _error_code(exc) in _MISSING_CODES:
                return None
            raise ObjectStorageError("object storage unavailable") from exc
        except BotoCoreError as exc:
            raise ObjectStorageError("object storage unavailable") from exc
        return ObjectStat(size_bytes=int(head["ContentLength"]))

    def delete_object(self, object_key: str) -> None:
        try:
            # S3 DeleteObject is idempotent: deleting a missing key succeeds.
            self._client.delete_object(Bucket=self._bucket, Key=object_key)
        except (ClientError, BotoCoreError) as exc:
            raise ObjectStorageError("object storage unavailable") from exc

    def reachable(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            return False


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))
