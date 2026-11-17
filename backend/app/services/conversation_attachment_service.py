"""Conversation Attachment Service.

Manages private uploaded documents attached directly to chat conversations,
handling extraction, chunking, chat-scoped search, and knowledge-base promotion.
"""

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.chunking.recursive import _split_text
from app.models.conversation import (
    Conversation,
    ConversationAttachment,
    ConversationAttachmentChunk,
)
from app.models.knowledge import Document, DocumentChunk, DocumentVersion, KnowledgeBase
from app.parsers import get_parser_registry
from app.storage import get_storage_provider, sanitize_filename
from app.vectorstores.base import VectorSearchResult

logger = logging.getLogger("mmaip.conversation_attachments")

MAX_ATTACHMENT_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
DEFAULT_DELIMITERS = ["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""]


class ConversationAttachmentService:
    """Service orchestrating conversation-scoped document uploads and intelligence."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id
        self.storage = get_storage_provider()
        self.parser_registry = get_parser_registry()
        self.delimiters = DEFAULT_DELIMITERS

    async def upload_attachment(
        self,
        conversation_id: uuid.UUID,
        uploader_user_id: Optional[uuid.UUID],
        filename: str,
        content: bytes,
        declared_content_type: Optional[str] = None,
    ) -> ConversationAttachment:
        """Validate, store, extract, and chunk an uploaded document for a conversation."""
        # 1. Size enforcement
        if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError(
                f"File size ({len(content)} bytes) exceeds the maximum allowed limit of {MAX_ATTACHMENT_SIZE_BYTES} bytes (25 MB)."
            )

        # 2. Sanitize filename and detect MIME type
        safe_name = sanitize_filename(filename)
        detected_mime = self.parser_registry.detect_mime_type(content, safe_name)
        mime_type = declared_content_type or detected_mime

        # 3. Resolve parser and validate magic signature
        parser = self.parser_registry.resolve_parser(safe_name, content, declared_mime=mime_type)

        # 4. Compute content hash
        file_hash = hashlib.sha256(content).hexdigest()
        attachment_id = uuid.uuid4()

        # 5. Persist to storage provider under tenant-prefixed private path
        relative_path = f"conversations/{conversation_id}/attachments/{attachment_id}_{safe_name}"
        stored_key = await self.storage.save(str(self.tenant_id), relative_path, content)

        # 6. Parse and extract text
        extracted_text = ""
        total_pages = 1
        page_chunks: list[tuple[str, int]] = []  # (text, page_number)

        try:
            parsed = await parser.extract(content, safe_name, mime_type=mime_type)
            extracted_text = parsed.text or ""
            if parsed.pages:
                total_pages = len(parsed.pages)
                for page in parsed.pages:
                    chunks = _split_text(page.text or "", self.delimiters, 800, 150)
                    for c in chunks:
                        if c.strip():
                            page_chunks.append((c.strip(), page.page_number))
            else:
                chunks = _split_text(extracted_text, self.delimiters, 800, 150)
                for c in chunks:
                    if c.strip():
                        page_chunks.append((c.strip(), 1))
        except Exception as p_err:
            logger.warning(f"Failed parsing attachment {safe_name}: {p_err}")
            extracted_text = content.decode("utf-8", errors="replace")[:10000]
            chunks = _split_text(extracted_text, self.delimiters, 800, 150)
            for c in chunks:
                if c.strip():
                    page_chunks.append((c.strip(), 1))

        # 7. Create ConversationAttachment record
        attachment = ConversationAttachment(
            id=attachment_id,
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            uploader_user_id=uploader_user_id,
            filename=safe_name,
            content_type=mime_type,
            file_size=len(content),
            file_path=stored_key,
            file_hash=file_hash,
            status="READY",
            extracted_text=extracted_text[:30000] if extracted_text else None,
            total_pages=total_pages,
            total_chunks=len(page_chunks),
            is_promoted=False,
            metadata_json={"detected_mime": detected_mime, "parser": parser.__class__.__name__},
        )
        self.session.add(attachment)

        # 8. Create searchable attachment chunks
        for idx, (chunk_text, page_num) in enumerate(page_chunks):
            chunk_rec = ConversationAttachmentChunk(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                attachment_id=attachment_id,
                conversation_id=conversation_id,
                chunk_index=idx,
                content=chunk_text,
                token_count=max(1, len(chunk_text) // 4),
                page_number=page_num,
                metadata_json={"page": page_num, "filename": safe_name},
            )
            self.session.add(chunk_rec)

        await self.session.commit()
        await self.session.refresh(attachment)
        return attachment

    async def list_attachments(self, conversation_id: uuid.UUID) -> list[ConversationAttachment]:
        """List active attachments for an authorized conversation."""
        stmt = (
            select(ConversationAttachment)
            .where(
                ConversationAttachment.conversation_id == conversation_id,
                ConversationAttachment.tenant_id == self.tenant_id,
            )
            .order_by(ConversationAttachment.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_attachment(
        self, conversation_id: uuid.UUID, attachment_id: uuid.UUID
    ) -> Optional[ConversationAttachment]:
        """Fetch a specific attachment with strict tenant and conversation scoping."""
        stmt = select(ConversationAttachment).where(
            ConversationAttachment.id == attachment_id,
            ConversationAttachment.conversation_id == conversation_id,
            ConversationAttachment.tenant_id == self.tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_attachment_bytes(
        self, conversation_id: uuid.UUID, attachment_id: uuid.UUID
    ) -> tuple[ConversationAttachment, bytes]:
        """Retrieve attachment metadata and raw binary content."""
        att = await self.get_attachment(conversation_id, attachment_id)
        if not att:
            raise ValueError("Attachment not found or access denied")
        data = await self.storage.get(str(self.tenant_id), att.file_path)
        return att, data

    async def delete_attachment(self, conversation_id: uuid.UUID, attachment_id: uuid.UUID) -> bool:
        """Delete an attachment, its searchable chunks, and private storage file."""
        att = await self.get_attachment(conversation_id, attachment_id)
        if not att:
            return False

        promoted_doc_exists = False
        if att.promoted_document_id:
            chk_stmt = select(Document.id).where(
                Document.id == att.promoted_document_id,
                Document.tenant_id == self.tenant_id,
            )
            promoted_doc_exists = (await self.session.execute(chk_stmt)).scalar_one_or_none() is not None

        if not promoted_doc_exists:
            try:
                await self.storage.delete(str(self.tenant_id), att.file_path)
            except Exception as s_err:
                logger.warning(f"Could not delete physical storage file {att.file_path}: {s_err}")
        else:
            logger.info(
                f"Preserving physical storage file {att.file_path} because attachment {att.id} "
                f"was promoted to Knowledge Base document {att.promoted_document_id}"
            )

        await self.session.delete(att)
        await self.session.commit()
        return True

    async def promote_to_knowledge_base(
        self,
        conversation_id: uuid.UUID,
        attachment_id: uuid.UUID,
        target_kb_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID],
        title: Optional[str] = None,
    ) -> tuple[ConversationAttachment, Document]:
        """Promote a chat attachment into a permanent Knowledge Base document."""
        att = await self.get_attachment(conversation_id, attachment_id)
        if not att:
            raise ValueError("Attachment not found or access denied")
        if att.promoted_document_id:
            raise ValueError(f"Attachment is already promoted to Knowledge Base document {att.promoted_document_id}")

        # 1. Authorize target Knowledge Base
        kb_stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == target_kb_id,
            KnowledgeBase.tenant_id == self.tenant_id,
            KnowledgeBase.status == "ACTIVE",
        )
        kb = (await self.session.execute(kb_stmt)).scalar_one_or_none()
        if not kb:
            raise ValueError("Target Knowledge Base not found or access denied")

        # 2. Fetch chunks from attachment
        chunks_stmt = (
            select(ConversationAttachmentChunk)
            .where(
                ConversationAttachmentChunk.attachment_id == attachment_id,
                ConversationAttachmentChunk.tenant_id == self.tenant_id,
            )
            .order_by(ConversationAttachmentChunk.chunk_index.asc())
        )
        att_chunks = (await self.session.execute(chunks_stmt)).scalars().all()

        # 3. Create Document in target Knowledge Base
        doc_id = uuid.uuid4()
        effective_filename = title.strip() if (title and title.strip()) else att.filename
        promoted_doc = Document(
            id=doc_id,
            tenant_id=self.tenant_id,
            knowledge_base_id=target_kb_id,
            filename=effective_filename,
            safe_filename=sanitize_filename(effective_filename),
            file_path=att.file_path,
            file_size=att.file_size,
            mime_type=att.content_type,
            file_hash=att.file_hash,
            status="READY",
            current_version_num=1,
            total_pages=att.total_pages,
            total_chunks=len(att_chunks),
            metadata_json={"source": "conversation_promotion", "conversation_id": str(conversation_id)},
            access_level=kb.access_level,
        )
        self.session.add(promoted_doc)

        # 4. Create DocumentVersion
        doc_version = DocumentVersion(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            document_id=doc_id,
            version_num=1,
            file_path=att.file_path,
            file_size=att.file_size,
            file_hash=att.file_hash,
            extracted_text=att.extracted_text,
            structured_data={},
            extraction_stats={"promoted_from_attachment_id": str(att.id)},
        )
        self.session.add(doc_version)
        for chk in att_chunks:
            doc_chunk = DocumentChunk(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                knowledge_base_id=target_kb_id,
                document_id=doc_id,
                document_version_id=doc_version.id,
                chunk_index=chk.chunk_index,
                content=chk.content,
                character_count=len(chk.content),
                token_count=chk.token_count,
                page_number=chk.page_number,
                chunking_strategy="conversation_attachment",
                metadata_json=chk.metadata_json,
            )
            self.session.add(doc_chunk)

        # Flush Document, Version, and Chunks so Foreign Key constraints are satisfied in Postgres
        await self.session.flush()

        # 6. Update attachment promotion status
        att.is_promoted = True
        att.promoted_knowledge_base_id = target_kb_id
        att.promoted_document_id = doc_id
        att.promoted_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(att)
        await self.session.refresh(promoted_doc)
        return att, promoted_doc

    async def search_attachment_chunks(
        self,
        conversation_id: uuid.UUID,
        query: str,
        top_k: int = 5,
    ) -> list[VectorSearchResult]:
        """Search chunks across all active attachments in this conversation using relevance ranking."""
        stmt = (
            select(ConversationAttachmentChunk, ConversationAttachment.filename)
            .join(ConversationAttachment, ConversationAttachmentChunk.attachment_id == ConversationAttachment.id)
            .where(
                ConversationAttachmentChunk.conversation_id == conversation_id,
                ConversationAttachmentChunk.tenant_id == self.tenant_id,
                ConversationAttachment.status == "READY",
            )
        )
        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return []

        # Tokenize query terms for BM25-style lexical scoring
        query_terms = set(re.findall(r"\w+", query.lower()))
        scored_chunks: list[tuple[float, ConversationAttachmentChunk, str]] = []

        for chunk, filename in rows:
            content_lower = chunk.content.lower()
            chunk_tokens = re.findall(r"\w+", content_lower)
            if not chunk_tokens:
                continue

            # Term overlap score + exact phrase matching boost
            matches = sum(1 for term in query_terms if term in content_lower)
            phrase_bonus = 2.0 if query.lower().strip() in content_lower else 0.0
            overlap_score = (matches / max(1, len(query_terms))) + phrase_bonus

            if overlap_score > 0:
                scored_chunks.append((overlap_score, chunk, filename))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_chunks[:top_k]

        results: list[VectorSearchResult] = []
        for score, chunk, filename in top_matches:
            results.append(
                VectorSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.attachment_id,
                    knowledge_base_id=chunk.conversation_id,
                    content=chunk.content,
                    score=float(score),
                    document_title=filename,
                    page_number=chunk.page_number,
                    heading_path=f"Attachment: {filename}",
                    metadata={"source": "conversation_attachment", "filename": filename, "page": chunk.page_number},
                )
            )

        return results
