"""Dependency-free, in-process first-stage rate limiting.

This module implements a conservative sliding-window limiter used to blunt
credential stuffing, registration abuse, anonymous public-chat floods, and
developer/upload spikes before expensive work (DB writes, quota reservations,
provider calls) is performed.

IMPORTANT (per-process limitation): state lives in this Python process only.
It is intentionally dependency-free (no Redis or other service). With multiple
workers/replicas each process keeps its own counters, so the effective global
limit is  (configured limit) x (number of worker processes). This is a
first-stage defence only; a shared store is required for a strict cluster-wide
limit.
"""

import asyncio
import hashlib
import logging
import math
import time
from collections import deque

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger("mmaip.core.rate_limit")

_MAX_TRACKED_KEYS = 10_000
_RATE_LIMIT_DETAIL = "Too many requests. Please try again later."


def _now() -> float:
    """Monotonic clock for the limiter. Tests monkeypatch this module attribute."""
    return time.monotonic()


class SlidingWindowLimiter:
    """Async-safe sliding-window limiter with bounded in-memory key storage.

    Each key maps to a deque of monotonic timestamps. ``check`` prunes events
    older than the window, denies when the window is full, and otherwise records
    the request. Keys are evicted in insertion order once ~10,000 keys are
    tracked so an attacker rotating identities cannot grow memory without bound.
    """

    def __init__(self, max_keys: int = _MAX_TRACKED_KEYS) -> None:
        self._max_keys = max(1, max_keys)
        self._events: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    def _evict_oldest_key(self) -> None:
        if not self._events:
            return
        oldest_key = next(iter(self._events))
        self._events.pop(oldest_key, None)

    async def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds) for one attempt under ``key``."""
        async with self._lock:
            now = _now()
            window = max(1, int(window_seconds))

            if key not in self._events and len(self._events) >= self._max_keys:
                self._evict_oldest_key()

            events = self._events.get(key)
            if events is None:
                events = deque()
                self._events[key] = events

            cutoff = now - window
            while events and events[0] <= cutoff:
                events.popleft()

            if limit <= 0:
                return False, window

            if len(events) >= limit:
                oldest = events[0]
                retry_after = max(1, math.ceil((oldest + window) - now))
                return False, retry_after

            events.append(now)
            return True, 0

    def reset(self) -> None:
        """Clear all tracked windows (used by tests and administrative resets)."""
        self._events.clear()


limiter = SlidingWindowLimiter()


def _hashed_key(action: str, identity: str) -> str:
    """Hash the action/identity pair so raw IPs, emails, or IDs are never retained."""
    return hashlib.sha256(f"{action}:{identity}".encode("utf-8")).hexdigest()


async def enforce_rate_limit(
    action: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Raise HTTP 429 when the identity exceeds the configured action limit."""
    if not settings.RATE_LIMIT_ENABLED:
        return

    key = _hashed_key(action, identity)
    allowed, retry_after = await limiter.check(key, limit, window_seconds)
    if allowed:
        return

    # Log only the action and an opaque key prefix; never the raw identity.
    logger.warning("Rate limit exceeded: action=%s key_prefix=%s", action, key[:12])
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=_RATE_LIMIT_DETAIL,
        headers={"Retry-After": str(retry_after)},
    )


def client_identity(request: Request) -> str:
    """Resolve the client identity, honoring X-Forwarded-For only for trusted proxies."""
    peer = request.client.host if request.client and request.client.host else "unknown"

    trusted = {part.strip() for part in (settings.TRUSTED_PROXY_IPS or "").split(",") if part.strip()}
    if peer in trusted:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first_hop = forwarded.split(",", 1)[0].strip()
            if first_hop:
                return first_hop

    return peer
