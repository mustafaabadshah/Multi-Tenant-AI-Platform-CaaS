import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AssistantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    llm_provider: str = Field(default="omniroute")
    default_model: str = Field(default="auto")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=64, le=8192)
    visibility: str = Field(default="workspace")
    retrieval_mode: str = Field(default="hybrid")
    top_k: int = Field(default=5, ge=1, le=20)
    system_prompt: Optional[str] = None
    knowledge_base_ids: list[uuid.UUID] = Field(default_factory=list)


class AssistantUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    description: Optional[str] = None
    llm_provider: Optional[str] = None
    default_model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=64, le=8192)
    visibility: Optional[str] = None
    retrieval_mode: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    system_prompt: Optional[str] = None
    status: Optional[str] = None
    knowledge_base_ids: Optional[list[uuid.UUID]] = None


class AssistantResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    llm_provider: str = "omniroute"
    default_model: str = "auto"
    temperature: float = 0.7
    max_tokens: int = 1024
    visibility: str = "workspace"
    retrieval_mode: str = "hybrid"
    top_k: int = 5
    system_prompt: Optional[str] = None
    status: str
    connected_kb_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreateRequest(BaseModel):
    assistant_id: uuid.UUID
    title: Optional[str] = Field(default="New Conversation", max_length=255)


class MessageCitationResponse(BaseModel):
    id: uuid.UUID
    citation_num: int = 1
    chunk_id: Optional[uuid.UUID] = None
    document_name: str
    citation_text: str
    page_number: Optional[int] = 1
    heading_path: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None
    bounding_box: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_type: str
    content: str
    token_count: int = 0
    citations: list[MessageCitationResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    assistant_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=16000)
