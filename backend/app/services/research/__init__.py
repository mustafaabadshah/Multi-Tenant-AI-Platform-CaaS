"""Research & Academic Literature Services."""

from app.services.research.academic_search import (
    detect_academic_search_intent,
    execute_academic_search_preflight,
)

__all__ = [
    "detect_academic_search_intent",
    "execute_academic_search_preflight",
]
