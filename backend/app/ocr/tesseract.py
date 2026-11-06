"""Tesseract OCR Provider for CPU-based local OCR."""

import asyncio
import io
import shutil
import time
from PIL import Image
import pymupdf
import pytesseract

from app.core.config import settings
from app.ocr.base import OCRConfiguration, OCRPageResult, OCRProvider, OCRResult


class TesseractOCRProvider(OCRProvider):
    """Local CPU-based OCR provider using Tesseract and PyMuPDF."""

    def __init__(self) -> None:
        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    @property
    def provider_name(self) -> str:
        return "tesseract"

    def is_available(self) -> bool:
        """Check if Tesseract binary is discoverable in PATH or configured command."""
        cmd = pytesseract.pytesseract.tesseract_cmd
        return bool(shutil.which(cmd) or (cmd and shutil.which("tesseract")))

    def _sync_ocr_image(self, img: Image.Image, lang: str) -> str:
        """Synchronous invocation of Tesseract image_to_string."""
        try:
            return pytesseract.image_to_string(img, lang=lang).strip()
        except pytesseract.TesseractNotFoundError:
            raise RuntimeError(
                "Tesseract executable was not found. Please install Tesseract-OCR and ensure it is in PATH "
                "or set TESSERACT_CMD in environment settings."
            )
        except Exception as e:
            raise RuntimeError(f"Tesseract OCR failed: {e}") from e

    async def process_pdf(
        self,
        pdf_bytes: bytes,
        scanned_page_numbers: list[int],
        config: OCRConfiguration,
    ) -> OCRResult:
        start_time = time.perf_counter()
        page_results: list[OCRPageResult] = []
        warnings: list[str] = []

        if not self.is_available():
            msg = (
                "Tesseract OCR is not installed or not in PATH. Scanned pages could not be recognized. "
                "To enable OCR, install Tesseract-OCR or configure TESSERACT_CMD."
            )
            return OCRResult(
                text="",
                pages=[],
                provider=self.provider_name,
                language=config.language,
                success=False,
                error_message=msg,
                warnings=[msg],
            )

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            return OCRResult(
                text="",
                pages=[],
                provider=self.provider_name,
                language=config.language,
                success=False,
                error_message=f"Failed to open PDF stream for OCR: {e}",
            )

        try:
            pages_to_process = scanned_page_numbers if scanned_page_numbers else list(range(1, len(doc) + 1))
            full_texts: list[str] = []

            for page_num in pages_to_process:
                if page_num < 1 or page_num > len(doc):
                    continue

                page = doc[page_num - 1]
                # Render page at 200 DPI for reliable OCR accuracy
                pix = page.get_pixmap(dpi=config.dpi or 200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                try:
                    ocr_text = await asyncio.to_thread(self._sync_ocr_image, img, config.language)
                except Exception as e:
                    warnings.append(f"Page {page_num} OCR failed: {e}")
                    ocr_text = ""

                page_results.append(
                    OCRPageResult(
                        page_number=page_num,
                        text=ocr_text,
                        provider=self.provider_name,
                        language=config.language,
                    )
                )
                if ocr_text:
                    full_texts.append(f"--- Page {page_num} [OCR] ---\n{ocr_text}")

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return OCRResult(
                text="\n\n".join(full_texts),
                pages=page_results,
                provider=self.provider_name,
                language=config.language,
                duration_ms=duration_ms,
                success=True,
                warnings=warnings,
            )
        finally:
            doc.close()

    async def process_images(
        self,
        images: list[bytes],
        config: OCRConfiguration,
    ) -> OCRResult:
        start_time = time.perf_counter()
        page_results: list[OCRPageResult] = []
        warnings: list[str] = []
        full_texts: list[str] = []

        if not self.is_available():
            msg = "Tesseract OCR is not installed or not in PATH."
            return OCRResult(
                text="",
                pages=[],
                provider=self.provider_name,
                language=config.language,
                success=False,
                error_message=msg,
                warnings=[msg],
            )

        for idx, img_bytes in enumerate(images):
            try:
                img = Image.open(io.BytesIO(img_bytes))
                ocr_text = await asyncio.to_thread(self._sync_ocr_image, img, config.language)
                page_results.append(
                    OCRPageResult(
                        page_number=idx + 1,
                        text=ocr_text,
                        provider=self.provider_name,
                        language=config.language,
                    )
                )
                if ocr_text:
                    full_texts.append(ocr_text)
            except Exception as e:
                warnings.append(f"Image {idx+1} OCR failed: {e}")

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return OCRResult(
            text="\n\n".join(full_texts),
            pages=page_results,
            provider=self.provider_name,
            language=config.language,
            duration_ms=duration_ms,
            success=True,
            warnings=warnings,
        )
