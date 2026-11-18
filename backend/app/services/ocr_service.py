"""Lightweight, CPU-friendly OCR Service for Multi-Tenant AI Platform (CaaS).

Supports extracting visible text from screenshots, scanned PDF pages, and document images
using local Tesseract OCR when available, with graceful degradation when the binary is absent.
"""

import asyncio
import io
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from PIL import Image

logger = logging.getLogger(__name__)

# Enforce decompression bomb limit (25 million pixels) to protect against memory exhaustion
Image.MAX_IMAGE_PIXELS = 25_000_000


@dataclass
class OCRResult:
    """Normalized OCR extraction result."""
    text: str = ""
    confidence: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    engine: str = "tesseract"
    dimensions: tuple[int, int] = (0, 0)


class OCRService:
    """Manages selective, resource-bounded OCR execution."""

    MAX_DIMENSION = 3000
    OCR_TIMEOUT_SECONDS = 15.0

    _test_ocr_handler: Optional[Callable[[bytes, str], str]] = None

    def __init__(self, tesseract_cmd: Optional[str] = None):
        self._custom_cmd = tesseract_cmd
        self._resolved_cmd: Optional[str] = None
        self._is_available: Optional[bool] = None

    @classmethod
    def set_test_ocr_handler(cls, handler: Optional[Callable[[bytes, str], str]]) -> None:
        """Inject a test handler for deterministic unit/integration testing without Tesseract."""
        cls._test_ocr_handler = handler

    def get_tesseract_path(self) -> Optional[str]:
        """Locate Tesseract executable on Windows, Linux/Docker, or via environment variables."""
        if self._resolved_cmd:
            return self._resolved_cmd

        env_cmd = os.environ.get("TESSERACT_CMD") or self._custom_cmd
        if env_cmd and os.path.exists(env_cmd):
            self._resolved_cmd = env_cmd
            return self._resolved_cmd

        # Check system PATH
        path_cmd = shutil.which("tesseract")
        if path_cmd:
            self._resolved_cmd = path_cmd
            return self._resolved_cmd

        # Standard Windows installation locations
        win_candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        ]
        for candidate in win_candidates:
            if os.path.exists(candidate):
                self._resolved_cmd = candidate
                return self._resolved_cmd

        # Standard Linux paths
        linux_candidates = ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]
        for candidate in linux_candidates:
            if os.path.exists(candidate):
                self._resolved_cmd = candidate
                return self._resolved_cmd

        return None

    def is_available(self) -> bool:
        """Check whether local OCR capability is operational."""
        if self._test_ocr_handler is not None:
            return True
        if self._is_available is None:
            self._is_available = self.get_tesseract_path() is not None
        return self._is_available

    async def extract_text_from_image_bytes(
        self,
        image_bytes: bytes,
        filename: str = "image.png",
        lang: str = "eng",
    ) -> OCRResult:
        """Extract text from raw image bytes with dimension bounds and timeout."""
        start_time = time.perf_counter()

        # Check for test handler hook
        test_handler = OCRService._test_ocr_handler
        if test_handler is not None:
            try:
                mock_text = test_handler(image_bytes, filename)
                elapsed = (time.perf_counter() - start_time) * 1000
                return OCRResult(
                    text=mock_text,
                    success=True,
                    execution_time_ms=elapsed,
                    engine="test_mock",
                    dimensions=(100, 100),
                )
            except Exception as e:
                elapsed = (time.perf_counter() - start_time) * 1000
                return OCRResult(
                    text="",
                    success=False,
                    error=str(e),
                    execution_time_ms=elapsed,
                    engine="test_mock",
                )

        if not self.is_available():
            elapsed = (time.perf_counter() - start_time) * 1000
            return OCRResult(
                text="",
                success=False,
                error="OCR_UNAVAILABLE",
                warnings=[
                    "OCR engine (Tesseract) is not installed on this system. "
                    "Scanned document pages and images will be indexed with metadata only."
                ],
                execution_time_ms=elapsed,
            )

        # Offload CPU work to threadpool to avoid blocking asyncio event loop
        return await asyncio.to_thread(self._sync_extract, image_bytes, filename, lang, start_time)

    def _sync_extract(
        self,
        image_bytes: bytes,
        filename: str,
        lang: str,
        start_time: float,
    ) -> OCRResult:
        warnings: list[str] = []
        try:
            image = Image.open(io.BytesIO(image_bytes))
            orig_w, orig_h = image.size

            # Safe downscaling if dimensions exceed MAX_DIMENSION
            if orig_w > self.MAX_DIMENSION or orig_h > self.MAX_DIMENSION:
                ratio = min(self.MAX_DIMENSION / orig_w, self.MAX_DIMENSION / orig_h)
                new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
                image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
                warnings.append(f"Image downscaled from {orig_w}x{orig_h} to {new_w}x{new_h} for OCR stability.")

            # Convert to RGB if needed (handles RGBA, Palette, 1-bit)
            if image.mode not in ("L", "RGB"):
                image = image.convert("RGB")

            import pytesseract

            tess_cmd = self.get_tesseract_path()
            if tess_cmd:
                pytesseract.pytesseract.tesseract_cmd = tess_cmd

            text = pytesseract.image_to_string(
                image,
                lang=lang,
                timeout=int(self.OCR_TIMEOUT_SECONDS),
            )
            clean_text = text.strip()

            elapsed = (time.perf_counter() - start_time) * 1000
            return OCRResult(
                text=clean_text,
                success=True,
                warnings=warnings,
                execution_time_ms=elapsed,
                engine="tesseract",
                dimensions=(orig_w, orig_h),
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.warning("OCR processing error for %s: %s", filename, exc)
            return OCRResult(
                text="",
                success=False,
                error=str(exc),
                warnings=warnings + [f"OCR extraction encountered an error: {exc}"],
                execution_time_ms=elapsed,
                engine="tesseract",
            )


_default_ocr_service = OCRService()


def get_ocr_service() -> OCRService:
    return _default_ocr_service
