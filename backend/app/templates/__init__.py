"""Templates package for versioned, data-driven assistant blueprints."""

from app.templates.registry import TemplateRegistry, get_template_registry
from app.templates.schema import AssistantTemplate, TemplateListResponse

__all__ = [
    "AssistantTemplate",
    "TemplateListResponse",
    "TemplateRegistry",
    "get_template_registry",
]
