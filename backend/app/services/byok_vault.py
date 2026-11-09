"""BYOK Key Vault Service managing secure encryption, rotation, and resolution of API credentials."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.llm.base import LLMConfig
from app.llm.registry import get_llm_registry
from app.models.provider import ProviderCredential

logger = logging.getLogger("mmaip.services.byok")


class BYOKVaultService:
    """Service managing encrypted provider credentials for multi-tenant workspaces."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def list_credentials(self) -> list[ProviderCredential]:
        """List all credentials for the tenant (secrets remain encrypted in DB, masked in schemas)."""
        stmt = (
            select(ProviderCredential)
            .where(ProviderCredential.tenant_id == self.tenant_id)
            .order_by(ProviderCredential.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_credential(self, credential_id: uuid.UUID) -> Optional[ProviderCredential]:
        """Get a single credential by ID with strict tenant scoping."""
        stmt = select(ProviderCredential).where(
            ProviderCredential.id == credential_id,
            ProviderCredential.tenant_id == self.tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_credential(
        self,
        provider_name: str,
        display_name: str,
        api_key: str,
        base_url: Optional[str] = None,
        is_default: bool = False,
    ) -> ProviderCredential:
        """Encrypt and store a provider credential."""
        p_name = provider_name.strip().lower()
        encrypted = encrypt_secret(api_key.strip())
        masked = mask_secret(api_key.strip())

        # If setting as default, clear previous defaults for this provider
        if is_default:
            await self.session.execute(
                update(ProviderCredential)
                .where(
                    ProviderCredential.tenant_id == self.tenant_id,
                    ProviderCredential.provider_name == p_name,
                )
                .values(is_default=False)
            )

        credential = ProviderCredential(
            tenant_id=self.tenant_id,
            provider_name=p_name,
            display_name=display_name.strip(),
            encrypted_api_key=encrypted,
            api_key_masked=masked,
            base_url=base_url.strip() if base_url else None,
            is_active=True,
            is_default=is_default,
            status="HEALTHY",
            last_tested_at=datetime.now(UTC),
        )
        self.session.add(credential)
        await self.session.commit()
        await self.session.refresh(credential)
        return credential

    async def test_credential(self, credential_id: uuid.UUID) -> tuple[bool, Optional[str]]:
        """Decrypt key in memory, test against provider endpoint, and update health status."""
        cred = await self.get_credential(credential_id)
        if not cred:
            return False, "Credential not found"

        plaintext_key = decrypt_secret(cred.encrypted_api_key)
        if not plaintext_key:
            cred.status = "UNHEALTHY"
            cred.error_message = "Failed to decrypt secret"
            await self.session.commit()
            return False, cred.error_message

        registry = get_llm_registry()
        try:
            provider = registry.get_provider(cred.provider_name, strict=True)
            cfg = LLMConfig(
                provider=cred.provider_name,
                api_key=plaintext_key,
                base_url=cred.base_url,
                timeout_seconds=10,
            )
            is_valid = await provider.validate_key(cfg)
            cred.last_tested_at = datetime.now(UTC)
            if is_valid:
                cred.status = "HEALTHY"
                cred.error_message = None
            else:
                cred.status = "UNHEALTHY"
                cred.error_message = "Provider endpoint rejected API key (HTTP 401/403 or network failure)"
            await self.session.commit()
            return is_valid, cred.error_message
        except Exception as exc:
            cred.status = "UNHEALTHY"
            cred.error_message = str(exc)
            await self.session.commit()
            return False, str(exc)

    async def rotate_credential(
        self,
        credential_id: uuid.UUID,
        new_api_key: str,
    ) -> Optional[ProviderCredential]:
        """Rotate an existing credential's key with in-memory encryption."""
        cred = await self.get_credential(credential_id)
        if not cred:
            return None

        cred.encrypted_api_key = encrypt_secret(new_api_key.strip())
        cred.api_key_masked = mask_secret(new_api_key.strip())
        cred.updated_at = datetime.now(UTC)
        cred.status = "HEALTHY"
        cred.error_message = None

        await self.session.commit()
        await self.session.refresh(cred)
        return cred

    async def revoke_credential(self, credential_id: uuid.UUID) -> Optional[ProviderCredential]:
        """Deactivate and revoke a credential immediately."""
        cred = await self.get_credential(credential_id)
        if not cred:
            return None
        cred.status = "REVOKED"
        cred.is_active = False
        cred.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(cred)
        return cred

    async def delete_credential(self, credential_id: uuid.UUID) -> bool:
        """Permanently delete a credential record."""
        stmt = delete(ProviderCredential).where(
            ProviderCredential.id == credential_id,
            ProviderCredential.tenant_id == self.tenant_id,
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount > 0

    async def resolve_plaintext_key(self, provider_name: str) -> tuple[Optional[str], Optional[str]]:
        """Resolve and decrypt the active or default API key and base_url for provider runtime calls."""
        p_name = provider_name.strip().lower()
        stmt = (
            select(ProviderCredential)
            .where(
                ProviderCredential.tenant_id == self.tenant_id,
                ProviderCredential.provider_name == p_name,
                ProviderCredential.is_active.is_(True),
                ProviderCredential.status != "REVOKED",
            )
            .order_by(ProviderCredential.is_default.desc(), ProviderCredential.updated_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        cred = res.scalar_one_or_none()
        if not cred:
            return None, None
        return decrypt_secret(cred.encrypted_api_key), cred.base_url
