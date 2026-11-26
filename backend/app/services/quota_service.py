import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.administration import QuotaReservation, TenantQuota
from app.models.assistant import Assistant
from app.models.conversation import ConversationAttachment
from app.models.knowledge import Document
from app.models.provider import ProviderUsageLog

logger = logging.getLogger("mmaip.services.quota")

DEFAULT_MONTHLY_TOKEN_LIMIT = 10_000_000  # 10M tokens
DEFAULT_DAILY_REQUEST_LIMIT = 2_000       # 2000 requests/day
RESERVATION_EXPIRATION_SECONDS = 300      # 5 minutes

# Thread-safe in-flight active reservations tracking
_active_reservations: dict[str, dict[str, Any]] = {}
_released_reservations: set[str] = set()
_reservations_lock = threading.Lock()


class QuotaService:
    """Enforces multi-tenant token/request quotas with PostgreSQL-backed atomic enforcement."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    @classmethod
    def release_reservation(cls, reservation_id: Optional[str]) -> None:
        """Safely release an in-flight token reservation."""
        if not reservation_id:
            return
        with _reservations_lock:
            _active_reservations.pop(reservation_id, None)
            _released_reservations.add(reservation_id)

    async def release_reservation_async(self, reservation_id: Optional[str]) -> None:
        """Atomically mark a reservation as RELEASED in PostgreSQL."""
        if not reservation_id:
            return
        self.release_reservation(reservation_id)
        try:
            clean_id = reservation_id.removeprefix("res_")
            res_uuid = uuid.UUID(clean_id)
            now = datetime.now(UTC)
            await self.session.execute(
                update(QuotaReservation)
                .where(
                    QuotaReservation.id == res_uuid,
                    QuotaReservation.tenant_id == self.tenant_id,
                    QuotaReservation.status == "ACTIVE",
                )
                .values(status="RELEASED", released_at=now)
                .execution_options(synchronize_session=False)
            )
            await self.session.commit()
        except Exception as exc:
            logger.debug("Failed async reservation release for %s: %s", reservation_id, exc)

    async def get_or_create_quota(self) -> TenantQuota:
        """Retrieve quota configuration or initialize default for tenant."""
        stmt = select(TenantQuota).where(TenantQuota.tenant_id == self.tenant_id)
        result = await self.session.execute(stmt)
        quota = result.scalar_one_or_none()
        if not quota:
            quota = TenantQuota(
                tenant_id=self.tenant_id,
                monthly_token_limit=DEFAULT_MONTHLY_TOKEN_LIMIT,
            )
            self.session.add(quota)
            await self.session.commit()
            await self.session.refresh(quota)
        return quota

    async def reserve_quota(self, estimated_tokens: int = 500) -> str:
        """Atomically verify limits including all in-flight requests and create a durable reservation."""
        quota = await self.get_or_create_quota()
        now = datetime.now(UTC)
        tid_str = str(self.tenant_id)

        # 1. Flush any locally released reservations to PostgreSQL
        with _reservations_lock:
            pending_releases = list(_released_reservations)
            _released_reservations.clear()

        if pending_releases:
            clean_uuids: list[uuid.UUID] = []
            for r_id in pending_releases:
                try:
                    clean_uuids.append(uuid.UUID(r_id.removeprefix("res_")))
                except (ValueError, TypeError):
                    pass
            if clean_uuids:
                await self.session.execute(
                    update(QuotaReservation)
                    .where(
                        QuotaReservation.id.in_(clean_uuids),
                        QuotaReservation.status == "ACTIVE",
                    )
                    .values(status="RELEASED", released_at=now)
                    .execution_options(synchronize_session=False)
                )

        # 2. Mark stale expired active reservations as EXPIRED in DB
        await self.session.execute(
            update(QuotaReservation)
            .where(
                QuotaReservation.tenant_id == self.tenant_id,
                QuotaReservation.status == "ACTIVE",
                QuotaReservation.expires_at < now,
            )
            .values(status="EXPIRED")
            .execution_options(synchronize_session=False)
        )

        # 3. Monthly token usage check from ProviderUsageLog
        start_of_month = datetime(now.year, now.month, 1, tzinfo=UTC)
        tokens_stmt = (
            select(func.coalesce(func.sum(ProviderUsageLog.total_tokens), 0))
            .where(
                ProviderUsageLog.tenant_id == self.tenant_id,
                ProviderUsageLog.created_at >= start_of_month,
            )
        )
        tokens_used_res = await self.session.execute(tokens_stmt)
        current_monthly_tokens = int(tokens_used_res.scalar_one())

        # 4. Daily request limit check from ProviderUsageLog
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=UTC)
        requests_stmt = (
            select(func.count(ProviderUsageLog.id))
            .where(
                ProviderUsageLog.tenant_id == self.tenant_id,
                ProviderUsageLog.created_at >= start_of_day,
            )
        )
        req_res = await self.session.execute(requests_stmt)
        today_requests = int(req_res.scalar_one())
        daily_limit = getattr(quota, "daily_request_limit", DEFAULT_DAILY_REQUEST_LIMIT)

        # 5. Query active durable reservations from DB
        active_res_stmt = (
            select(
                func.coalesce(func.sum(QuotaReservation.tokens_reserved), 0),
                func.count(QuotaReservation.id),
            )
            .where(
                QuotaReservation.tenant_id == self.tenant_id,
                QuotaReservation.status == "ACTIVE",
                QuotaReservation.expires_at >= now,
            )
        )
        active_res_row = (await self.session.execute(active_res_stmt)).one()
        db_in_flight_tokens = int(active_res_row[0])
        db_in_flight_requests = int(active_res_row[1])

        # Also blend in-process memory reservations if uncommitted
        with _reservations_lock:
            curr_time = time.time()
            stale = [k for k, v in _active_reservations.items() if curr_time - v.get("created_at", 0) > RESERVATION_EXPIRATION_SECONDS]
            for s in stale:
                _active_reservations.pop(s, None)
            mem_in_flight_tokens = sum(
                r["tokens"] for r in _active_reservations.values() if r["tenant_id"] == tid_str
            )
            mem_in_flight_requests = sum(
                1 for r in _active_reservations.values() if r["tenant_id"] == tid_str
            )

        in_flight_tokens = max(db_in_flight_tokens, mem_in_flight_tokens)
        in_flight_requests = max(db_in_flight_requests, mem_in_flight_requests)

        # Check monthly token capacity
        if (current_monthly_tokens + in_flight_tokens + estimated_tokens) > quota.monthly_token_limit:
            logger.warning(
                f"Tenant {self.tenant_id} exceeded monthly token quota (including in-flight): "
                f"{current_monthly_tokens + in_flight_tokens}/{quota.monthly_token_limit} tokens"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Monthly token limit exceeded ({current_monthly_tokens + in_flight_tokens:,} of "
                    f"{quota.monthly_token_limit:,} tokens used/reserved). Please increase quota or add BYOK key."
                ),
            )

        # Check daily request capacity
        if (today_requests + in_flight_requests) >= daily_limit:
            logger.warning(
                f"Tenant {self.tenant_id} exceeded daily request limit (including in-flight): "
                f"{today_requests + in_flight_requests}/{daily_limit}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Daily request quota reached ({today_requests + in_flight_requests:,} of {daily_limit:,} requests). "
                    f"Quota resets tomorrow at 00:00 UTC."
                ),
            )

        # Create durable reservation in PostgreSQL
        res_uuid = uuid.uuid4()
        res_id = f"res_{res_uuid.hex}"
        reservation = QuotaReservation(
            id=res_uuid,
            tenant_id=self.tenant_id,
            tokens_reserved=estimated_tokens,
            status="ACTIVE",
            expires_at=now + timedelta(seconds=RESERVATION_EXPIRATION_SECONDS),
        )
        self.session.add(reservation)
        await self.session.commit()
        await self.session.refresh(reservation)

        with _reservations_lock:
            _active_reservations[res_id] = {
                "tenant_id": tid_str,
                "tokens": estimated_tokens,
                "created_at": time.time(),
            }

        return res_id

    async def check_quota(self, estimated_tokens: int = 500) -> None:
        """Enforce quota limits server-side (legacy compatibility)."""
        res_id = await self.reserve_quota(estimated_tokens)
        self.release_reservation(res_id)
        await self.release_reservation_async(res_id)

    async def record_usage(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        user_id: Optional[uuid.UUID] = None,
        assistant_id: Optional[uuid.UUID] = None,
        is_estimated: bool = False,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        is_preview: bool = False,
        credential_source: str = "byok",
        traffic_type: str = "internal",
        reservation_id: Optional[str] = None,
    ) -> ProviderUsageLog:
        """Atomically persist fine-grained usage consumption and release any in-flight reservation."""
        p = (provider or provider_name or "omniroute").lower()
        m = model or model_name or "auto"
        total = prompt_tokens + completion_tokens
        usage_log = ProviderUsageLog(
            tenant_id=self.tenant_id,
            user_id=user_id,
            assistant_id=assistant_id,
            provider=p,
            model=m,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            is_estimated=is_estimated,
            credential_source=credential_source,
            traffic_type=traffic_type,
        )

        now = datetime.now(UTC)
        try:
            self.session.add(usage_log)
            if reservation_id:
                try:
                    clean_id = reservation_id.removeprefix("res_")
                    res_uuid = uuid.UUID(clean_id)
                    await self.session.execute(
                        update(QuotaReservation)
                        .where(
                            QuotaReservation.id == res_uuid,
                            QuotaReservation.tenant_id == self.tenant_id,
                            QuotaReservation.status == "ACTIVE",
                        )
                        .values(status="CONSUMED", consumed_at=now)
                        .execution_options(synchronize_session=False)
                    )
                except (ValueError, TypeError):
                    pass

            await self.session.commit()
            await self.session.refresh(usage_log)
            return usage_log
        finally:
            if reservation_id:
                self.release_reservation(reservation_id)

    async def get_usage_summary(self) -> dict[str, Any]:
        """Aggregate usage summary for the tenant dashboard."""
        now = datetime.now(UTC)
        start_of_month = datetime(now.year, now.month, 1, tzinfo=UTC)
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=UTC)

        quota = await self.get_or_create_quota()

        # Monthly total tokens
        tokens_stmt = select(
            func.coalesce(func.sum(ProviderUsageLog.total_tokens), 0),
            func.coalesce(func.sum(ProviderUsageLog.prompt_tokens), 0),
            func.coalesce(func.sum(ProviderUsageLog.completion_tokens), 0),
        ).where(
            ProviderUsageLog.tenant_id == self.tenant_id,
            ProviderUsageLog.created_at >= start_of_month,
        )
        res = await self.session.execute(tokens_stmt)
        month_total, month_prompt, month_comp = res.one()

        # Today's total requests
        requests_stmt = select(func.count(ProviderUsageLog.id)).where(
            ProviderUsageLog.tenant_id == self.tenant_id,
            ProviderUsageLog.created_at >= start_of_day,
        )
        req_res = await self.session.execute(requests_stmt)
        today_req_count = int(req_res.scalar_one())

        # Breakdown by provider
        provider_breakdown_stmt = (
            select(
                ProviderUsageLog.provider,
                func.sum(ProviderUsageLog.total_tokens),
                func.count(ProviderUsageLog.id),
            )
            .where(
                ProviderUsageLog.tenant_id == self.tenant_id,
                ProviderUsageLog.created_at >= start_of_month,
            )
            .group_by(ProviderUsageLog.provider)
        )
        p_res = await self.session.execute(provider_breakdown_stmt)
        by_provider = [
            {"provider": row[0], "tokens": int(row[1] or 0), "requests": int(row[2] or 0)}
            for row in p_res.all()
        ]

        # Breakdown by traffic_type
        traffic_breakdown_stmt = (
            select(
                ProviderUsageLog.traffic_type,
                func.sum(ProviderUsageLog.total_tokens),
                func.count(ProviderUsageLog.id),
            )
            .where(
                ProviderUsageLog.tenant_id == self.tenant_id,
                ProviderUsageLog.created_at >= start_of_month,
            )
            .group_by(ProviderUsageLog.traffic_type)
        )
        t_res = await self.session.execute(traffic_breakdown_stmt)
        by_traffic_type = [
            {"traffic_type": row[0], "tokens": int(row[1] or 0), "requests": int(row[2] or 0)}
            for row in t_res.all()
        ]

        daily_limit = getattr(quota, "daily_request_limit", DEFAULT_DAILY_REQUEST_LIMIT)
        pct_used = (month_total / quota.monthly_token_limit * 100) if quota.monthly_token_limit > 0 else 0

        # Storage calculation (Knowledge Base documents + conversation attachments)
        doc_stmt = select(
            func.coalesce(func.sum(Document.file_size), 0),
            func.count(Document.id),
        ).where(
            Document.tenant_id == self.tenant_id,
            Document.status != "DELETED",
        )
        doc_res = await self.session.execute(doc_stmt)
        doc_bytes, doc_count = doc_res.one()

        att_stmt = select(
            func.coalesce(func.sum(ConversationAttachment.file_size), 0),
            func.count(ConversationAttachment.id),
        ).where(ConversationAttachment.tenant_id == self.tenant_id)
        att_res = await self.session.execute(att_stmt)
        att_bytes, att_count = att_res.one()

        total_storage_bytes = int(doc_bytes) + int(att_bytes)
        total_documents = int(doc_count) + int(att_count)

        # Active assistants count
        asst_stmt = select(func.count(Assistant.id)).where(
            Assistant.tenant_id == self.tenant_id,
            Assistant.status != "DELETED",
        )
        asst_res = await self.session.execute(asst_stmt)
        active_assistants = int(asst_res.scalar_one())

        # Next month reset timestamp calculation
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1, tzinfo=UTC)
        else:
            next_month = datetime(now.year, now.month + 1, 1, tzinfo=UTC)

        return {
            "monthly_tokens_used": int(month_total),
            "monthly_tokens_limit": quota.monthly_token_limit,
            "monthly_prompt_tokens": int(month_prompt),
            "monthly_completion_tokens": int(month_comp),
            "percentage_used": round(pct_used, 1),
            "today_requests": today_req_count,
            "daily_request_limit": daily_limit,
            "by_provider": by_provider,
            "by_traffic_type": by_traffic_type,
            "storage_bytes_used": total_storage_bytes,
            "storage_bytes_limit": getattr(quota, "max_storage_bytes", 10_737_418_240),
            "document_count": total_documents,
            "document_limit": 500,
            "active_assistants": active_assistants,
            "max_assistants": getattr(quota, "max_assistants", 10),
            "measurement_timestamp": now.isoformat(),
            "reset_timestamp": next_month.isoformat(),
        }
