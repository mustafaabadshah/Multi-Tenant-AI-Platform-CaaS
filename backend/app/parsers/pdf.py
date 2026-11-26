"""PDF Document Parser using PyMuPDF (fitz)."""

import time

import pymupdf

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
)


class PDFParser(DocumentParser):
    """Secure PDF parser using PyMuPDF."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".pdf"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {"application/pdf", "application/x-pdf"}

    @property
    def parser_name(self) -> str:
        return "PyMuPDF_Parser"

    @property
    def parser_version(self) -> str:
        return f"pymupdf-{pymupdf.__version__}"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate PDF magic bytes (%PDF-)."""
        return content.startswith(b"%PDF-")

    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        start_time = time.perf_counter()
        warnings: list[str] = []
        pages: list[ExtractedPage] = []
        sections: list[ExtractedSection] = []
        all_text_parts: list[str] = []

        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
        except Exception as e:
            raise ValueError(f"Failed to open PDF document: {e}") from e

        try:
            metadata = doc.metadata or {}
            title = metadata.get("title") or filename

            # Extract table of contents if available
            toc = doc.get_toc() or []
            for item in toc:
                # item: [lvl, title, page, ...]
                if len(item) >= 3:
                    lvl, heading_title, page_num = item[0], item[1], item[2]
                    sections.append(
                        ExtractedSection(
                            heading=heading_title,
                            level=lvl,
                            page_number=page_num,
                        )
                    )

            has_scanned_pages = False
            total_images = 0
            MAX_OCR_PAGES_PER_DOC = 5
            ocr_pages_processed = 0
            from app.services.ocr_service import get_ocr_service
            ocr_service = get_ocr_service()

            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_num = page_idx + 1
                page_text = page.get_text("text").strip()
                image_list = page.get_images(full=True)
                images_count = len(image_list)
                total_images += images_count

                # Scanned page heuristic: has images but very little extractable text
                is_scanned = images_count > 0 and len(page_text) < 40
                ocr_derived = False

                if is_scanned:
                    has_scanned_pages = True
                    if ocr_pages_processed < MAX_OCR_PAGES_PER_DOC:
                        try:
                            pix = page.get_pixmap(dpi=150)
                            img_bytes = pix.tobytes("png")
                            ocr_res = await ocr_service.extract_text_from_image_bytes(
                                img_bytes,
                                filename=f"{filename}_page_{page_num}.png",
                            )
                            if ocr_res.text:
                                page_text = ocr_res.text.strip()
                                ocr_derived = True
                                ocr_pages_processed += 1
                            if ocr_res.warnings:
                                warnings.extend(ocr_res.warnings)
                        except Exception as ocr_err:
                            warnings.append(f"Selective OCR failed for page {page_num}: {ocr_err}")

                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text=page_text,
                        is_scanned=is_scanned,
                        images_count=images_count,
                        metadata={"ocr_derived": ocr_derived},
                    )
                )

                if page_text:
                    prefix = f"--- Page {page_num} [OCR Derived] ---\n" if ocr_derived else f"--- Page {page_num} ---\n"
                    all_text_parts.append(f"{prefix}{page_text}")
                elif is_scanned:
                    all_text_parts.append(f"--- Page {page_num} [Scanned/Image Page] ---")

            if has_scanned_pages and ocr_pages_processed == 0:
                warnings.append("Document contains scanned or image-based pages. Install Tesseract OCR to enable text extraction from images.")

            full_text = "\n\n".join(all_text_parts)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return ExtractedDocument(
                source_filename=filename,
                mime_type=mime_type or "application/pdf",
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                title=title,
                text=full_text,
                pages=pages,
                sections=sections,
                metadata={
                    "author": metadata.get("author"),
                    "creator": metadata.get("creator"),
                    "producer": metadata.get("producer"),
                    "creation_date": metadata.get("creationDate"),
                    "pages_count": len(pages),
                    "total_images": total_images,
                },
                warnings=warnings,
                extraction_stats={
                    "duration_ms": duration_ms,
                    "pages_count": len(pages),
                    "char_count": len(full_text),
                    "has_scanned_pages": has_scanned_pages,
                },
            )
        finally:
            doc.close()
