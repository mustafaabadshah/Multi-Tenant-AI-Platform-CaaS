"""S3-compatible object storage provider (AWS S3, MinIO, Cloudflare R2, Supabase Storage)."""

import os
from contextlib import asynccontextmanager
from typing import NoReturn, Optional

from app.core.config import settings
from app.storage.base import (
    StorageError,
    StorageNotFoundError,
    StorageProvider,
    StorageUnavailableError,
)

_NOT_FOUND_CODES = frozenset({"nosuchkey", "notfound", "404", "nosuchversion"})
_BUCKET_UNAVAILABLE_CODES = frozenset({"nosuchbucket", "nosuchbucketpolicy"})
_AUTH_CODES = frozenset(
    {
        "accessdenied",
        "accessdeniedexception",
        "403",
        "forbidden",
        "invalidaccesskeyid",
        "signaturedoesnotmatch",
        "expiredtoken",
        "invalidtoken",
        "unauthorized",
        "401",
        "invalidclienttokenid",
        "missingsecurityheader",
        "accountproblem",
        "allaccessdisabled",
    }
)
_THROTTLE_CODES = frozenset(
    {
        "slowdown",
        "throttling",
        "throttlingexception",
        "requestlimitexceeded",
        "toomanyrequests",
        "429",
        "503",
        "serviceunavailable",
        "internalerror",
        "requesttimeout",
        "provisionedthroughputexceededexception",
    }
)
_NETWORK_EXC_NAMES = frozenset(
    {
        "endpointconnectionerror",
        "connecttimeouterror",
        "readtimeouterror",
        "connectionclosederror",
        "httpclienterror",
        "proxyconnectionerror",
        "sslerror",
        "responsestreamingerror",
        "incompletereaderror",
        "protocolerror",
        "newconnectionerror",
        "maxretryerror",
        "nameresolutionerror",
        "connectionerror",
        "connectionreseterror",
        "brokenpipeerror",
        "timeouterror",
    }
)
_AUTH_EXC_NAMES = frozenset(
    {
        "nocredentialserror",
        "partialcredentialserror",
        "credentialretrievalerror",
        "tokenretrievalerror",
        "ssotokenloaderror",
        "unauthorizedssotokenerror",
    }
)


def _error_code(exc: BaseException) -> str | None:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error")
        if isinstance(error, dict):
            code = error.get("Code")
            if code:
                return str(code)
    code = getattr(exc, "code", None)
    if code:
        return str(code)
    return None


def _http_status(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        metadata = response.get("ResponseMetadata")
        if isinstance(metadata, dict):
            status = metadata.get("HTTPStatusCode")
            if isinstance(status, int):
                return status
    for attribute in ("status_code", "status"):
        raw_status = getattr(exc, attribute, None)
        if raw_status is None:
            continue
        try:
            return int(raw_status)
        except (TypeError, ValueError):
            continue
    return None


def _error_detail(exc: BaseException, code: str | None, status: int | None) -> str:
    parts = [type(exc).__name__]
    if code:
        parts.append(f"code={code}")
    if status is not None:
        parts.append(f"status={status}")
    return ", ".join(parts)


def _classify_s3_error(operation: str, exc: BaseException) -> StorageError:
    """Map a provider exception onto the typed storage error hierarchy.

    Only genuine object-not-found responses become ``StorageNotFoundError``.
    Authentication, authorization, network, timeout, throttling, and provider
    5xx failures become ``StorageUnavailableError`` so callers never interpret
    an inaccessible object as an absent one.
    """
    if isinstance(exc, StorageError):
        return exc

    code = _error_code(exc)
    normalized_code = (code or "").lower()
    status = _http_status(exc)
    exc_name = type(exc).__name__.lower()
    detail = _error_detail(exc, code, status)

    if exc_name in _AUTH_EXC_NAMES:
        return StorageUnavailableError(f"S3 {operation} failed: credentials unavailable ({detail}).")

    if exc_name in _NETWORK_EXC_NAMES or any(
        token in exc_name for token in ("timeout", "connection", "endpoint")
    ):
        return StorageUnavailableError(f"S3 {operation} failed: storage unreachable ({detail}).")

    if normalized_code in _BUCKET_UNAVAILABLE_CODES:
        return StorageUnavailableError(
            f"S3 {operation} failed: bucket unavailable ({detail})."
        )

    if normalized_code in _AUTH_CODES or status in (401, 403):
        return StorageUnavailableError(
            f"S3 {operation} failed: access denied or invalid credentials ({detail})."
        )

    if normalized_code in _NOT_FOUND_CODES or status == 404:
        return StorageNotFoundError(f"S3 {operation} failed: object not found ({detail}).")

    if normalized_code in _THROTTLE_CODES or status in (429, 500, 502, 503, 504):
        return StorageUnavailableError(
            f"S3 {operation} failed: provider throttled or unavailable ({detail})."
        )

    # Any other structured provider response is an availability problem: the
    # provider received the request but could not answer it safely. Only
    # exceptions with no provider response are treated as unexpected errors.
    if isinstance(getattr(exc, "response", None), dict):
        return StorageUnavailableError(
            f"S3 {operation} failed with a provider error ({detail})."
        )

    return StorageError(f"S3 {operation} failed with an unexpected error ({detail}).")


def _raise_storage_error(operation: str, exc: BaseException) -> NoReturn:
    raise _classify_s3_error(operation, exc) from exc


class S3StorageProvider(StorageProvider):
    """S3-compatible object storage provider with tenant key isolation.

    Keys are isolated under the tenant prefix: `{tenant_id}/{relative_key}`.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None,
    ) -> None:
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME or os.environ.get("S3_BUCKET_NAME")
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL or os.environ.get("S3_ENDPOINT_URL")
        self.access_key_id = (
            access_key_id or settings.S3_ACCESS_KEY_ID or os.environ.get("S3_ACCESS_KEY_ID")
        )
        self.secret_access_key = (
            secret_access_key or settings.S3_SECRET_ACCESS_KEY or os.environ.get("S3_SECRET_ACCESS_KEY")
        )
        self.region_name = (
            region_name or settings.S3_REGION_NAME or os.environ.get("S3_REGION_NAME", "us-east-1")
        )

    def _get_full_key(self, tenant_id: str, relative_key: str) -> str:
        segments = [
            seg
            for seg in relative_key.replace("\\", "/").split("/")
            if seg not in ("", ".", "..")
        ]
        clean_key = "/".join(segments)
        return f"{tenant_id}/{clean_key}"

    def _check_configured(self) -> None:
        if not self.bucket_name:
            raise ValueError(
                "S3 storage backend selected, but S3_BUCKET_NAME is not configured. "
                "Please configure S3_BUCKET_NAME in environment."
            )

    @asynccontextmanager
    async def _client(self):
        try:
            import aioboto3
        except ImportError as exc:
            raise ImportError(
                "aioboto3 is required for S3StorageProvider. Install it via `pip install aioboto3`."
            ) from exc

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
        ) as s3_client:
            yield s3_client

    async def save(self, tenant_id: str, relative_key: str, data: bytes) -> str:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            async with self._client() as s3_client:
                await s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=full_key,
                    Body=data,
                )
        except Exception as exc:
            _raise_storage_error("put_object", exc)
        return full_key

    async def get(self, tenant_id: str, relative_key: str) -> bytes:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            async with self._client() as s3_client:
                resp = await s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
                if not isinstance(resp, dict) or "Body" not in resp:
                    raise StorageError("S3 get_object returned an unexpected response.")
                async with resp["Body"] as stream:
                    return await stream.read()
        except Exception as exc:
            _raise_storage_error("get_object", exc)

    async def delete(self, tenant_id: str, relative_key: str) -> bool:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            async with self._client() as s3_client:
                await s3_client.delete_object(Bucket=self.bucket_name, Key=full_key)
        except Exception as exc:
            mapped = _classify_s3_error("delete_object", exc)
            if isinstance(mapped, StorageNotFoundError):
                return False
            raise mapped from exc
        return True

    async def exists(self, tenant_id: str, relative_key: str) -> bool:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            async with self._client() as s3_client:
                await s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
        except Exception as exc:
            mapped = _classify_s3_error("head_object", exc)
            if isinstance(mapped, StorageNotFoundError):
                return False
            raise mapped from exc
        return True

    async def get_size(self, tenant_id: str, relative_key: str) -> int:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            async with self._client() as s3_client:
                resp = await s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
                return int(resp.get("ContentLength", 0))
        except Exception as exc:
            _raise_storage_error("head_object", exc)

    async def list_keys(self, tenant_id: str, prefix: str = "") -> list[str]:
        """List object keys under the tenant prefix, relative to the storage root.

        S3 stores objects as ``{tenant_id}/{relative_key}``; this method strips
        that tenant prefix so returned keys match ``Document.file_path``.
        """
        self._check_configured()
        tenant_prefix = f"{tenant_id}/"
        keys: list[str] = []
        try:
            async with self._client() as s3_client:
                paginator = s3_client.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=tenant_prefix):
                    for item in page.get("Contents") or []:
                        full_key = item.get("Key", "")
                        if not full_key.startswith(tenant_prefix):
                            continue
                        relative = full_key[len(tenant_prefix):]
                        if prefix and not relative.startswith(prefix):
                            continue
                        keys.append(relative)
        except Exception as exc:
            _raise_storage_error("list_objects_v2", exc)

        return sorted(keys)
