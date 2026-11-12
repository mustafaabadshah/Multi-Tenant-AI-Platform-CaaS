"""Centralized CORS origin policy for the MMAIP backend.

Single source of truth for origin allowlists and the development-only
private-network regex, so CORS behavior is consistent and testable
independent of app bootstrap.
"""

from app.core.config import Settings

# Regex matching localhost and private LAN development origins.
DEV_ORIGIN_REGEX = (
    r"^https?://(localhost|127\.0\.0\.1|172\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$"
)

# Origins always allowed for local development tooling (Next.js dev server).
DEFAULT_DEV_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def _is_local_origin(origin: str) -> bool:
    return origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")


def build_cors_policy(settings: Settings) -> tuple[list[str], str | None]:
    """Compute (allow_origins, allow_origin_regex) for the given settings.

    Development:
      - localhost dev origins are always allowed;
      - the private-network LAN regex is applied only when the environment is
        development AND ``ALLOW_DEV_LAN_ORIGINS`` is explicitly enabled.

    Production/staging:
      - only explicitly configured origins (``FRONTEND_URL`` + ``ALLOWED_ORIGINS``)
        and the configured production origin regex are trusted;
      - localhost/LAN origins are rejected;
      - a missing or wildcard CORS configuration raises ``RuntimeError`` so the
        application fails clearly instead of shipping a permissive default.

    Returns a tuple of (origins, regex) suitable for ``CORSMiddleware``.
    """
    origins: list[str] = []
    if settings.FRONTEND_URL:
        origins.append(settings.FRONTEND_URL)
    for raw in (settings.ALLOWED_ORIGINS or "").split(","):
        cleaned = raw.strip()
        if cleaned and cleaned not in origins:
            origins.append(cleaned)

    is_dev = settings.ENVIRONMENT == "development"

    if is_dev:
        for default_origin in DEFAULT_DEV_ORIGINS:
            if default_origin not in origins:
                origins.append(default_origin)
        origin_regex: str | None = DEV_ORIGIN_REGEX if settings.ALLOW_DEV_LAN_ORIGINS else None
        return origins, origin_regex

    # Production / staging policy: explicit and fail-closed.
    if any(_is_local_origin(origin) for origin in origins):
        raise RuntimeError(
            "Invalid production CORS configuration: localhost/LAN origins are not allowed "
            "in production. Set FRONTEND_URL to the production HTTPS origin."
        )

    if "*" in origins:
        raise RuntimeError(
            "Invalid production CORS configuration: wildcard origin '*' cannot be combined "
            "with credentialed requests. Configure explicit trusted origins instead."
        )

    origin_regex = settings.CORS_ORIGIN_REGEX or None
    if not origins and not origin_regex:
        raise RuntimeError(
            "Invalid production CORS configuration: no trusted origins configured. "
            "Set FRONTEND_URL and/or ALLOWED_ORIGINS (and optionally CORS_ORIGIN_REGEX)."
        )

    return origins, origin_regex
