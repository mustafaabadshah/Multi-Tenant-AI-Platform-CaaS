"""Base interfaces and models for the OCR subsystem."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OCRConfiguration:
    """Configuration for OCR processing."""
    enabled: bool = False
    provider: str = "tesseract"
    language: str = "eng"
    dpi: int = 200
    timeout_seconds: int = 60
    custom_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRPageResult:
    """OCR result for a single document page or image."""
    page_number: int
    text: str
    confidence: float | None = None
    provider: str = ""
    language: str = "eng"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRResult:
    """Aggregate OCR result across document pages."""
    text: str
    pages: list[OCRPageResult] = field(default_factory=list)
    provider: str = ""
    language: str = "eng"
    duration_ms: int = 0
    success: bool = True
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)


class OCRProvider(ABC):
    """Abstract OCR Provider interface."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the OCR provider."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider dependencies and credentials are functional."""
        pass

    @abstractmethod
    async def process_pdf(
        self,
        pdf_bytes: bytes,
        scanned_page_numbers: list[int],
        config: OCRConfiguration,
    ) -> OCRResult:
        """Perform OCR on specific scanned pages of a PDF document."""
        pass

    @abstractmethod
    async def process_images(
        self,
        images: list[bytes],
        config: OCRConfiguration,
    ) -> OCRResult:
        """Perform OCR directly on image files."""
        pass
