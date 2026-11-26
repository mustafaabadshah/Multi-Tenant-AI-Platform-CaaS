"""Pydantic schemas for conversation attachments, knowledge promotion, and voice preferences."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConversationAttachmentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: Optional[uuid.UUID] = None
    uploader_user_id: Optional[uuid.UUID] = None
    filename: str
    content_type: str
    file_size: int
    status: str
    total_pages: int = 1
    total_chunks: int = 0
    is_promoted: bool = False
    promoted_knowledge_base_id: Optional[uuid.UUID] = None
    promoted_document_id: Optional[uuid.UUID] = None
    promoted_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationAttachmentChunkResponse(BaseModel):
    id: uuid.UUID
    attachment_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    page_number: Optional[int] = None

    model_config = {"from_attributes": True}


class AttachmentPromotionRequest(BaseModel):
    knowledge_base_id: Optional[uuid.UUID] = Field(default=None, description="Target Knowledge Base ID to promote attachment into")
    target_knowledge_base_id: Optional[uuid.UUID] = Field(default=None, description="Target Knowledge Base ID alias")
    title: Optional[str] = Field(default=None, description="Optional custom title for the promoted Knowledge Base document")


class AttachmentPromotionResponse(BaseModel):
    attachment_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    status: str = "PROMOTED"
    message: str = "Attachment successfully promoted to knowledge base"
    promoted_at: Optional[datetime] = None


class VoicePreferenceResponse(BaseModel):
    user_id: uuid.UUID
    voice_mode: str = "TEXT"
    auto_read: bool = False
    speech_rate: float = 1.0
    preferred_voice: Optional[str] = None
    preferred_language: str = "en-US"

    model_config = {"from_attributes": True}


class VoicePreferenceUpdateRequest(BaseModel):
    voice_mode: Optional[str] = Field(default=None, pattern="^(TEXT|DICTATION|LISTEN|VOICE_CONVERSATION)$")
    auto_read: Optional[bool] = None
    speech_rate: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    preferred_voice: Optional[str] = None
    preferred_language: Optional[str] = Field(default=None, max_length=20)
