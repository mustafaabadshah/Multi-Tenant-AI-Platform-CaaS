"""OCR subsystem package exports."""

from app.ocr.badho import BadhoOCRProvider
from app.ocr.base import (
    OCRConfiguration,
    OCRPageResult,
    OCRProvider,
    OCRResult,
)
from app.ocr.registry import OCRProviderRegistry, get_ocr_registry
from app.ocr.tesseract import TesseractOCRProvider

__all__ = [
    "BadhoOCRProvider",
    "OCRConfiguration",
    "OCRPageResult",
    "OCRProvider",
    "OCRProviderRegistry",
    "OCRResult",
    "TesseractOCRProvider",
    "get_ocr_registry",
]
