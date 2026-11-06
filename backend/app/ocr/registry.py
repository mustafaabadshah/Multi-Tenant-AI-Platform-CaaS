"""OCR Provider Registry."""

from app.ocr.badho import BadhoOCRProvider
from app.ocr.base import OCRProvider
from app.ocr.tesseract import TesseractOCRProvider


class OCRProviderRegistry:
    """Registry managing OCR providers."""

    def __init__(self) -> None:
        self._providers: dict[str, OCRProvider] = {
            "tesseract": TesseractOCRProvider(),
            "badho": BadhoOCRProvider(),
        }

    def register(self, provider: OCRProvider) -> None:
        self._providers[provider.provider_name.lower()] = provider

    def get_provider(self, name: str) -> OCRProvider:
        key = name.lower()
        if key not in self._providers:
            available = ", ".join(self._providers.keys())
            raise ValueError(f"Unknown OCR provider '{name}'. Available providers: {available}")
        return self._providers[key]

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())


_default_ocr_registry = OCRProviderRegistry()


def get_ocr_registry() -> OCRProviderRegistry:
    return _default_ocr_registry
