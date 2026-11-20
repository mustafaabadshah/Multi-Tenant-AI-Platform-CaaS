"""Data-driven Assistant Template Schemas."""

from typing import Literal
from pydantic import BaseModel, Field


class AssistantTemplate(BaseModel):
    id: str = Field(..., description="Unique immutable template identifier")
    name: str = Field(..., description="Human-readable template name")
    description: str = Field(..., description="Purpose summary for users")
    category: Literal["Education", "Business", "Personal", "Domain"] = Field(
        ..., description="Broad category group"
    )
    version: str = Field(default="1.0.0", description="Semantic template version")
    intended_audience: str = Field(
        default="general",
        description="Target user profile (e.g. students, employees, researchers, customers)",
    )
    default_instructions: str = Field(
        ..., description="Base system instructions embodying the persona, role, and guardrails"
    )
    default_response_style: str = Field(
        default="balanced",
        description="Response structure (e.g. socratic, concise, detailed, professional, friendly)",
    )
    default_uncertainty_behavior: str = Field(
        default="admit",
        description="Handling of missing knowledge (e.g. admit, clarify, synthesize)",
    )
    default_citation_style: str = Field(
        default="strict",
        description="Citation requirement (e.g. strict, general, none)",
    )
    suggested_knowledge: list[str] = Field(
        default_factory=list,
        description="Examples of relevant documents (e.g. Syllabus, Lecture Slides)",
    )
    suggested_starter_questions: list[str] = Field(
        default_factory=list,
        description="Helpful initial conversation questions for test & user experience",
    )
    default_retrieval_mode: str = Field(
        default="hybrid",
        description="Recommended retrieval mode (hybrid, semantic, lexical)",
    )
    default_top_k: int = Field(default=5, description="Recommended retrieval chunk count")
    default_temperature: float = Field(
        default=0.4, description="Recommended model generation temperature"
    )
    requires_knowledge: bool = Field(
        default=False, description="Whether knowledge is strictly required (always False; knowledge is optional)"
    )


class TemplateListResponse(BaseModel):
    templates: list[AssistantTemplate]
    total: int
    categories: list[str]
