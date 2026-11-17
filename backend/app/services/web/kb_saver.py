"""Knowledge Base Saver for Web Sources (M27).

Saves authorized web sources into workspace Knowledge Bases as Reference bookmarks
or Full-Content indexed documents without database migrations.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, DocumentChunk, DocumentVersion, KnowledgeBase
from app.services.conversation_attachment_service import sanitize_filename


class WebSaveMode(str, Enum):
    """Storage mode for saving web sources to a Knowledge Base."""
    REFERENCE = "REFERENCE"
    FULL_CONTENT = "FULL_CONTENT"


class WebKBSaveService:
    """Safely saves web sources into a designated Knowledge Base."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, user_id: Optional[uuid.UUID] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def save_web_source_to_kb(
        self,
        url: str,
        knowledge_base_id: uuid.UUID,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        extracted_text: Optional[str] = None,
        mode: str = "REFERENCE",
        storage_mode: Optional[str | WebSaveMode] = None,
    ) -> dict[str, Any]:
        """Save a web source into a tenant-authorized Knowledge Base."""
        canonical_url = url.strip()
        domain = urlparse(canonical_url).netloc.lower()

        raw_mode = storage_mode.value if isinstance(storage_mode, WebSaveMode) else (storage_mode or mode)
        normalized_mode = str(raw_mode).upper()
        if normalized_mode not in ("REFERENCE", "FULL_CONTENT"):
            normalized_mode = "REFERENCE"

        # 1. Authorize destination Knowledge Base
        kb_stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.tenant_id == self.tenant_id,
            KnowledgeBase.status == "ACTIVE",
        )
        kb = (await self.session.execute(kb_stmt)).scalar_one_or_none()
        if not kb:
            raise ValueError("Target Knowledge Base not found or access unauthorized.")

        # 2. Check for existing Document for this URL in this KB (Deduplication)
        doc_stmt = select(Document).where(
            Document.knowledge_base_id == knowledge_base_id,
            Document.tenant_id == self.tenant_id,
            Document.file_path == canonical_url,
            Document.status != "DELETED",
        )
        existing_doc = (await self.session.execute(doc_stmt)).scalar_one_or_none()

        clean_title = (title or "").strip()
        if not clean_title:
            clean_title = existing_doc.filename if existing_doc else f"Web Source ({domain})"

        clean_title = clean_title[:255]

        # 3. Create or Update Document
        if existing_doc:
            doc = existing_doc
            doc.filename = clean_title
            doc.updated_at = datetime.now(timezone.utc)
            meta = doc.metadata_json or {}
            meta.update({
                "storage_mode": normalized_mode,
                "notes": notes or meta.get("notes"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            doc.metadata_json = meta
        else:
            safe_name = sanitize_filename(clean_title)[:255] or f"web_{uuid.uuid4().hex[:8]}.html"
            doc = Document(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                knowledge_base_id=knowledge_base_id,
                filename=clean_title,
                safe_filename=safe_name,
                file_path=canonical_url,
                mime_type="text/html",
                file_size=len(extracted_text.encode("utf-8")) if extracted_text else 0,
                status="PROCESSED",
                access_level="tenant",
                total_chunks=0,
                metadata_json={
                    "source_type": "web",
                    "source_url": canonical_url,
                    "domain": domain,
                    "storage_mode": normalized_mode,
                    "notes": notes,
                    "user_id": str(self.user_id) if self.user_id else None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.session.add(doc)
            await self.session.flush()

        doc_id = doc.id

        # 4. Handle Chunks and Versioning based on mode
        chunks_to_create: list[str] = []
        if normalized_mode == "FULL_CONTENT" and extracted_text and extracted_text.strip():
            # Chunking extracted text into safe bounded paragraphs (~1000 chars)
            paragraphs = [p.strip() for p in extracted_text.split("\n\n") if p.strip()]
            cur_chunk = ""
            for p in paragraphs:
                if len(cur_chunk) + len(p) < 1000:
                    cur_chunk += ("\n\n" if cur_chunk else "") + p
                else:
                    if cur_chunk:
                        chunks_to_create.append(cur_chunk)
                    cur_chunk = p
            if cur_chunk:
                chunks_to_create.append(cur_chunk)

        doc.total_chunks = len(chunks_to_create)

        stored_text = extracted_text if normalized_mode == "FULL_CONTENT" else (notes or "")
        content_bytes = (stored_text or canonical_url).encode("utf-8")
        file_hash = hashlib.sha256(content_bytes).hexdigest()

        doc_version = DocumentVersion(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            document_id=doc_id,
            version_num=1,
            file_path=canonical_url,
            file_size=len(content_bytes),
            file_hash=file_hash,
            extracted_text=stored_text,
            structured_data={"domain": domain, "mode": normalized_mode},
            extraction_stats={"source": "web_intelligence", "mode": normalized_mode},
        )
        self.session.add(doc_version)

        # 5. Create DocumentChunks
        for c_idx, chunk_content in enumerate(chunks_to_create):
            doc_chunk = DocumentChunk(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                knowledge_base_id=knowledge_base_id,
                document_id=doc_id,
                document_version_id=doc_version.id,
                chunk_index=c_idx,
                content=chunk_content,
                character_count=len(chunk_content),
                token_count=max(1, len(chunk_content) // 4),
                page_number=1,
                chunking_strategy="web_source",
                metadata_json={
                    "source_type": "web",
                    "source_url": canonical_url,
                    "domain": domain,
                    "title": clean_title,
                },
            )
            self.session.add(doc_chunk)

        await self.session.flush()
        await self.session.commit()

        return {
            "document_id": str(doc.id),
            "knowledge_base_id": str(knowledge_base_id),
            "title": clean_title,
            "url": canonical_url,
            "domain": domain,
            "mode": normalized_mode,
            "storage_mode": normalized_mode,
            "total_chunks": len(chunks_to_create),
            "chunks_created": len(chunks_to_create),
            "status": "SUCCESS",
            "message": f"Web source '{clean_title}' saved successfully as {normalized_mode} in Knowledge Base.",
        }
