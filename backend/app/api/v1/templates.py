"""REST API router for data-driven assistant templates."""

from fastapi import APIRouter, HTTPException, status

from app.templates.registry import get_template_registry
from app.templates.schema import AssistantTemplate, TemplateListResponse

router = APIRouter(prefix="/templates", tags=["Assistant Templates"])


@router.get("", response_model=TemplateListResponse)
async def list_templates() -> TemplateListResponse:
    """Retrieve all available data-driven assistant templates grouped by category."""
    registry = get_template_registry()
    templates = registry.get_all()
    categories = registry.get_categories()
    return TemplateListResponse(
        templates=templates,
        total=len(templates),
        categories=categories,
    )


@router.get("/{template_id}", response_model=AssistantTemplate)
async def get_template(template_id: str) -> AssistantTemplate:
    """Retrieve details, default instructions, and parameters for a specific template."""
    registry = get_template_registry()
    tmpl = registry.get_by_id(template_id)
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id '{template_id}' not found",
        )
    return tmpl
