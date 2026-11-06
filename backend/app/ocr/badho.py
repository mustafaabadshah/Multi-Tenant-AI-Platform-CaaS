"""Badho OCR Provider Integration Placeholder.

HONEST INTEGRATION STATUS:
The platform architecture specifies support for Badho OCR. However, as verified during
the Pre-Implementation Audit, no official API documentation, OpenAPI specification,
authentication schema (e.g. bearer token, basic auth, HMAC), endpoint URLs, or client
SDK exist in the repository or local configuration.

To prevent sending confidential tenant documents to unverified endpoints or inventing
fictitious protocols, this provider acts as an explicit integration boundary. It safely
reports its blocked status until valid API specifications and credentials are provided.
"""

from app.core.config import settings
from app.ocr.base import OCRConfiguration, OCRPageResult, OCRProvider, OCRResult


class BadhoOCRProvider(OCRProvider):
    """Integration placeholder for Badho OCR."""

    @property
    def provider_name(self) -> str:
        return "badho"

    def is_available(self) -> bool:
        """Returns True only if both API URL and API Key are explicitly configured."""
        return bool(settings.BADHO_OCR_API_URL and settings.BADHO_OCR_API_KEY)

    async def process_pdf(
        self,
        pdf_bytes: bytes,
        scanned_page_numbers: list[int],
        config: OCRConfiguration,
    ) -> OCRResult:
        """Process scanned PDF pages via Badho OCR."""
        if not self.is_available():
            msg = (
                "Badho OCR integration is not operational: missing verified endpoint URL and API credentials. "
                "Required settings: BADHO_OCR_API_URL, BADHO_OCR_API_KEY. "
                "Official payload schemas and auth contracts are required before live requests can be dispatched."
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

        # Once official documentation is supplied:
        # 1. Prepare multipart upload or base64 payload per spec
        # 2. Dispatch HTTP POST to settings.BADHO_OCR_API_URL with auth headers
        # 3. Parse JSON response into OCRPageResult items
        raise NotImplementedError("Badho OCR live dispatch is pending official API documentation and schemas.")

    async def process_images(
        self,
        images: list[bytes],
        config: OCRConfiguration,
    ) -> OCRResult:
        """Process image bytes via Badho OCR."""
        if not self.is_available():
            msg = (
                "Badho OCR integration is not operational: missing verified endpoint URL and API credentials. "
                "Please configure BADHO_OCR_API_URL and BADHO_OCR_API_KEY."
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
        raise NotImplementedError("Badho OCR live dispatch is pending official API documentation.")
