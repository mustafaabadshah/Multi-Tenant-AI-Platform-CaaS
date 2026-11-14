"""Observability policy management, privacy-safe sanitization, and error categorization."""

import html
import re
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trace import ObservabilityPolicy


class ErrorCategory:
    AUTH_ERROR = "AUTH_ERROR"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    INVALID_CONFIG = "INVALID_CONFIG"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
    CANCELLED_STREAM = "CANCELLED_STREAM"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def categorize_error(err: Any) -> tuple[str, str]:
    """Convert an exception or error message into a standardized ErrorCategory and sanitized summary.

    Returns:
        tuple[str, str]: (category_code, safe_summary)
    """
    if err is None:
        return ErrorCategory.INTERNAL_ERROR, "Unknown failure"

    msg = str(err)

    # 1. Cancelled stream
    if "GeneratorExit" in msg or "cancelled" in msg.lower() or "client disconnected" in msg.lower():
        return ErrorCategory.CANCELLED_STREAM, "Request stream was cancelled or disconnected by the client."

    # 2. Quota exceeded
    if "quota exceeded" in msg.lower():
        clean_detail = re.sub(r"quota exceeded:?\s*", "", msg, flags=re.IGNORECASE).strip()
        return ErrorCategory.QUOTA_EXCEEDED, f"Workspace quota exceeded: {clean_detail or 'limit reached'}"

    # 3. Auth / BYOK missing
    if "byok" in msg.lower() or "not configured with an active byok" in msg.lower():
        return ErrorCategory.AUTH_ERROR, "Provider credential is not configured or active for this workspace."
    if "401" in msg or "unauthorized" in msg.lower() or "invalid api key" in msg.lower():
        return ErrorCategory.AUTH_ERROR, "Authentication failed with upstream provider."

    # 4. Rate limited
    if "429" in msg or "rate limit" in msg.lower() or "too many requests" in msg.lower():
        return ErrorCategory.RATE_LIMITED, "Provider rate limit reached. Please retry after a brief delay."

    # 5. Empty response
    if "empty response stream" in msg.lower():
        return ErrorCategory.EMPTY_RESPONSE, "LLM provider returned an empty response stream."

    # 6. Context overflow
    if "context length" in msg.lower() or "maximum context" in msg.lower() or "token limit" in msg.lower():
        return ErrorCategory.CONTEXT_OVERFLOW, "Request exceeded model context window limit."

    # 7. Provider unavailable or timeout
    if "timeout" in msg.lower() or "timed out" in msg.lower() or "deadline exceeded" in msg.lower():
        return ErrorCategory.PROVIDER_TIMEOUT, "Provider stream timed out."
    if "500" in msg or "502" in msg or "503" in msg or "unavailable" in msg.lower() or "connection error" in msg.lower():
        return ErrorCategory.PROVIDER_UNAVAILABLE, "Upstream AI provider is temporarily unavailable."

    # 8. Retrieval error
    if "retrieval" in msg.lower() or "vector store" in msg.lower() or "embedding" in msg.lower():
        return ErrorCategory.RETRIEVAL_ERROR, "Knowledge retrieval failed during request execution."

    # 9. Generic / Internal
    sanitized = sanitize_value(msg)
    # Strip any potential internal file paths
    sanitized = re.sub(r"[A-Za-z]:\\[\w\-\\]+\.py", "[internal_code]", str(sanitized))
    sanitized = re.sub(r"\/[\w\-\/]+\.py", "[internal_code]", str(sanitized))
    return ErrorCategory.INTERNAL_ERROR, f"Internal processing error: {sanitized[:180]}"


def sanitize_value(val: Any) -> Any:
    """Recursively redact sensitive tokens, passwords, and API keys."""
    if isinstance(val, str):
        # 1. Private key blocks (multiline)
        val = re.sub(
            r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----",
            "[REDACTED_PRIVATE_KEY]",
            val,
        )
        # 2. Database connection strings with credentials: postgresql://user:pass@host/db
        val = re.sub(
            r"(postgres(?:ql)?|mysql|sqlite|redis|mongodb):\/\/([^:\s\/]+):([^@\s\/]+)@([^\s\/]+)",
            r"\1://\2:[REDACTED_DB_CREDENTIALS]@\4",
            val,
            flags=re.IGNORECASE,
        )
        # 3. JWT tokens: eyJ...
        val = re.sub(
            r"\beyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]+\b",
            "[REDACTED_JWT_TOKEN]",
            val,
        )
        # 4. API keys & vendor tokens (OpenAI, Anthropic, Render, B2, platform keys)
        val = re.sub(r"\b(sk-[a-zA-Z0-9_\-]{8,})\b", "[REDACTED_API_KEY]", val)
        val = re.sub(r"\b(rnd_[a-zA-Z0-9]{10,})\b", "[REDACTED_API_KEY]", val)
        val = re.sub(r"\b(K00[a-zA-Z0-9]{20,})\b", "[REDACTED_B2_KEY]", val)
        val = re.sub(r"\b(mmaip_(live|test)_[a-zA-Z0-9_\-]{8,})\b", "[REDACTED_API_KEY]", val)
        # 5. Bearer & Authorization headers
        val = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{12,}", r"\1[REDACTED_TOKEN]", val, flags=re.IGNORECASE)
        val = re.sub(r"(Authorization\s*:\s*)(Basic|Bearer)\s+[^\s]+", r"\1\2 [REDACTED_AUTH]", val, flags=re.IGNORECASE)
        # 6. JSON, YAML, Env key-value password/secret assignments
        val = re.sub(
            r"([\"']?(?:password|pwd|secret|api_key|token|auth_token|access_key|app_key)[\"']?\s*[:=]\s*)[\"']?[^'\"\s\n,}]+[\"']?",
            r"\1[REDACTED]",
            val,
            flags=re.IGNORECASE,
        )
        return val
    elif isinstance(val, dict):
        return {
            k: sanitize_value(v)
            for k, v in val.items()
            if not any(s in k.lower() for s in ["password", "secret", "token", "auth_header", "private_key", "api_key", "access_key"])
        }
    elif isinstance(val, list):
        return [sanitize_value(item) for item in val]
    return val


def sanitize_preview(text: Optional[str], max_length: int = 250) -> Optional[str]:
    """Sanitize and truncate text for safe telemetry preview inspection."""
    if not text:
        return None

    # Scrub secrets
    cleaned = sanitize_value(text)

    # Scrub script and HTML tags to prevent XSS in dashboards
    cleaned = re.sub(r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "[SCRUBBED_SCRIPT]", cleaned, flags=re.IGNORECASE)
    cleaned = html.escape(cleaned)

    # Truncate
    if len(cleaned) > max_length:
        return cleaned[:max_length].rstrip() + " ... [truncated]"
    return cleaned


class ObservabilityPolicyService:
    """Service to fetch or manage tenant-level observability and preview policy."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def get_policy(self) -> ObservabilityPolicy:
        """Fetch tenant policy or return default policy."""
        stmt = select(ObservabilityPolicy).where(ObservabilityPolicy.tenant_id == self.tenant_id)
        res = await self.session.execute(stmt)
        policy = res.scalar_one_or_none()
        if not policy:
            policy = ObservabilityPolicy(
                tenant_id=self.tenant_id,
                capture_mode="METADATA_ONLY",
                max_preview_length=250,
                retention_days=30,
            )
        return policy

    async def update_policy(
        self,
        capture_mode: Optional[str] = None,
        max_preview_length: Optional[int] = None,
        retention_days: Optional[int] = None,
    ) -> ObservabilityPolicy:
        """Upsert tenant observability policy."""
        stmt = select(ObservabilityPolicy).where(ObservabilityPolicy.tenant_id == self.tenant_id)
        res = await self.session.execute(stmt)
        policy = res.scalar_one_or_none()

        if not policy:
            policy = ObservabilityPolicy(
                tenant_id=self.tenant_id,
                capture_mode="METADATA_ONLY",
                max_preview_length=250,
                retention_days=30,
            )
            self.session.add(policy)

        if capture_mode in ("METADATA_ONLY", "REDACTED_PREVIEW"):
            policy.capture_mode = capture_mode
        if max_preview_length is not None and 50 <= max_preview_length <= 500:
            policy.max_preview_length = max_preview_length
        if retention_days is not None and 7 <= retention_days <= 90:
            policy.retention_days = retention_days

        await self.session.commit()
        await self.session.refresh(policy)
        return policy
