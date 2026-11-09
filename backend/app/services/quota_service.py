"""Usage Accounting and Server-Side Quota Enforcement Service."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.administration import TenantQuota
from app.models.provider import ProviderUsageLog

logger = logging.getLogger("mmaip.services.quota")

DEFAULT_MONTHLY_TOKEN_LIMIT = 10_000_000  # 10M tokens
DEFAULT_DAILY_REQUEST_LIMIT = 2_000       # 2000 requests/day


class QuotaService:
    """Enforces multi-tenant token/request quotas and records provider consumption."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def get_or_create_quota(self) -> TenantQuota:
        """Retrieve quota configuration or initialize default for tenant."""
        stmt = select(TenantQuota).where(TenantQuota.tenant_id == self.tenant_id)
        result = await self.session.execute(stmt)
        quota = result.scalar_one_or_none()
        if not quota:
            quota = TenantQuota(
                tenant_id=self.tenant_id,
                monthly_token_limit=DEFAULT_MONTHLY_TOKEN_LIMIT,
                daily_request_limit=DEFAULT_DAILY_REQUEST_LIMIT,
            )
            self.session.add(quota)
            await self.session.commit()
            await self.session.refresh(quota)
        return quota

    async def check_quota(self, estimated_tokens: int = 500) -> None:
        """Enforce quota limits server-side BEFORE invoking any external provider.

        Raises HTTPException 429 if the tenant has exhausted monthly tokens or daily requests.
        """
        quota = await self.get_or_create_quota()
        now = datetime.now(UTC)

        # 1. Monthly token usage check
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

        if (current_monthly_tokens + estimated_tokens) > quota.monthly_token_limit:
            logger.warning(
                f"Tenant {self.tenant_id} exceeded monthly token quota: "
                f"{current_monthly_tokens}/{quota.monthly_token_limit} tokens"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Monthly token limit exceeded ({current_monthly_tokens:,} of "
                    f"{quota.monthly_token_limit:,} tokens used). Please increase quota or add BYOK key."
                ),
            )

        # 2. Daily request limit check
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
        if today_requests >= daily_limit:
            logger.warning(
                f"Tenant {self.tenant_id} exceeded daily request limit: "
                f"{today_requests}/{daily_limit}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Daily request quota reached ({today_requests:,} of {daily_limit:,} requests). "
                    f"Quota resets tomorrow at 00:00 UTC."
                ),
            )

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
    ) -> ProviderUsageLog:
        """Atomically persist fine-grained usage consumption."""
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
        )
        self.session.add(usage_log)
        await self.session.commit()
        await self.session.refresh(usage_log)
        return usage_log

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

        daily_limit = getattr(quota, "daily_request_limit", DEFAULT_DAILY_REQUEST_LIMIT)
        pct_used = (month_total / quota.monthly_token_limit * 100) if quota.monthly_token_limit > 0 else 0

        return {
            "monthly_tokens_used": int(month_total),
            "monthly_tokens_limit": quota.monthly_token_limit,
            "monthly_prompt_tokens": int(month_prompt),
            "monthly_completion_tokens": int(month_comp),
            "percentage_used": round(pct_used, 1),
            "today_requests": today_req_count,
            "daily_request_limit": daily_limit,
            "by_provider": by_provider,
        }
