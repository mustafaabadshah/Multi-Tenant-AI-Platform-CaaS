"""Shared hard resource limits for the ingestion pipeline.

The API upload path, the ingestion service, and the queue dispatcher all use
this module so a limit can never drift between entry points.

Text policy: extracted text is truncated at a UTF-8 character boundary instead
of rejected. A large but otherwise valid document still produces a bounded
version, and the stored/embedded text can never exceed
``MAX_EXTRACTED_TEXT_SIZE_BYTES``. Truncation is recorded as an ingestion event.
"""

from __future__ import annotations

import asyncio
import inspect
import io
import zipfile
from pathlib import PurePosixPath
from typing import Any

import pymupdf

UPLOAD_READ_CHUNK_SIZE = 64 * 1024
MAX_ARCHIVE_MEMBERS = 10_000
ZIP_BASED_EXTENSIONS = frozenset({".docx", ".xlsx", ".xlsm", ".pptx"})
PDF_EXTENSIONS = frozenset({".pdf"})
OOXML_MIME_PREFIX = "application/vnd.openxmlformats-officedocument"


class UploadTooLargeError(ValueError):
    """Raised when a streamed upload exceeds the configured byte budget."""


class IngestionLimitExceededError(Exception):
    """A permanent, non-retryable ingestion resource-limit violation."""


class IngestionTimeoutError(Exception):
    """A processing stage exceeded its deadline.

    Python threads cannot be force-killed. ``asyncio.wait_for`` stops awaiting
    the worker at the deadline, but parser or OCR code already executing in a
    thread keeps running until it returns on its own. The bound is therefore
    cooperative at await boundaries, not a hard kill.
    """


PERMANENT_INGESTION_ERRORS = (IngestionLimitExceededError, IngestionTimeoutError)


async def read_upload_bounded(
    upload_file: Any,
    max_bytes: int,
    chunk_size: int = UPLOAD_READ_CHUNK_SIZE,
) -> bytes:
    """Read an async upload stream in bounded chunks, rejecting oversized input.

    The stream is never read with an unbounded ``read()`` call. Memory stays
    bounded by ``max_bytes`` plus at most one chunk, and the caller receives
    no partial content when the budget is exceeded.
    """
    budget = max(0, int(max_bytes))
    size = max(1, int(chunk_size))
    buffer = bytearray()

    while True:
        chunk = await upload_file.read(size)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > budget:
            raise UploadTooLargeError(
                f"File exceeds the maximum permitted size of {budget} bytes."
            )

    return bytes(buffer)


def _validate_member_name(name: str) -> None:
    """Reject absolute, traversal, and otherwise unsafe ZIP member names."""
    normalized = name.replace("\\", "/")
    if not normalized or "\x00" in normalized:
        raise IngestionLimitExceededError("Archive contains an unsafe member name.")
    if normalized.startswith("/"):
        raise IngestionLimitExceededError("Archive contains an absolute member path.")
    if len(normalized) >= 2 and normalized[1] == ":":
        raise IngestionLimitExceededError("Archive contains an absolute member path.")
    if ".." in PurePosixPath(normalized).parts:
        raise IngestionLimitExceededError("Archive contains a path traversal member.")


def validate_zip_archive(content: bytes, max_expansion_bytes: int) -> dict[str, int]:
    """Inspect ZIP members before any extraction or parsing.

    Sums declared uncompressed sizes from the central directory and rejects the
    archive when the budget is exceeded or a member name is unsafe. No member
    content is extracted here.
    """
    budget = max(0, int(max_expansion_bytes))

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise IngestionLimitExceededError(
                    f"Archive contains {len(members)} members, exceeding the "
                    f"maximum of {MAX_ARCHIVE_MEMBERS}."
                )

            total_uncompressed = 0
            for member in members:
                _validate_member_name(member.filename)
                file_mode = (member.external_attr >> 16) & 0o170000
                if file_mode == 0o120000:
                    raise IngestionLimitExceededError(
                        "Archive contains a symbolic link member."
                    )
                total_uncompressed += max(0, int(member.file_size))
                if total_uncompressed > budget:
                    raise IngestionLimitExceededError(
                        f"Archive expands to more than the maximum permitted "
                        f"{budget} bytes."
                    )
    except zipfile.BadZipFile as exc:
        raise IngestionLimitExceededError(
            "Uploaded file is not a valid ZIP-based document container."
        ) from exc
    except OSError as exc:
        raise IngestionLimitExceededError(
            "Uploaded ZIP-based document container could not be inspected."
        ) from exc

    return {"archive_members": len(members), "archive_uncompressed_bytes": total_uncompressed}


def is_zip_based_document(filename: str, mime_type: str | None) -> bool:
    ext = PurePosixPath((filename or "").replace("\\", "/")).suffix.lower()
    if ext in ZIP_BASED_EXTENSIONS:
        return True
    return (mime_type or "").lower().startswith(OOXML_MIME_PREFIX)


def is_pdf_document(filename: str, mime_type: str | None, content: bytes) -> bool:
    ext = PurePosixPath((filename or "").replace("\\", "/")).suffix.lower()
    if ext in PDF_EXTENSIONS:
        return True
    if "pdf" in (mime_type or "").lower():
        return True
    return content.startswith(b"%PDF-")


def count_pdf_pages(content: bytes) -> int | None:
    """Return the PDF page count, or ``None`` when the stream cannot be opened."""
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except Exception:
        return None

    try:
        return int(document.page_count)
    finally:
        document.close()


def count_ooxml_pages(content: bytes, filename: str) -> int | None:
    """Count PPTX slides or XLSX worksheets from the ZIP directory, if applicable."""
    ext = PurePosixPath((filename or "").replace("\\", "/")).suffix.lower()
    if ext == ".pptx":
        prefix = "ppt/slides/slide"
    elif ext in {".xlsx", ".xlsm"}:
        prefix = "xl/worksheets/sheet"
    else:
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return None

    count = 0
    for name in names:
        if not name.startswith(prefix) or not name.endswith(".xml"):
            continue
        remainder = name[len(prefix) : -len(".xml")]
        if remainder.isdigit():
            count += 1
    return count


def enforce_pre_extraction_limits(
    filename: str,
    content: bytes,
    mime_type: str | None,
    *,
    max_archive_expansion_bytes: int,
    max_document_pages: int,
) -> dict[str, Any]:
    """Cheap pre-parse checks for ZIP expansion and PDF page count."""
    details: dict[str, Any] = {}
    page_limit = max(1, int(max_document_pages))

    if is_zip_based_document(filename, mime_type):
        details.update(validate_zip_archive(content, max_archive_expansion_bytes))
        ooxml_pages = count_ooxml_pages(content, filename)
        if ooxml_pages is not None:
            if ooxml_pages > page_limit:
                raise IngestionLimitExceededError(
                    f"Document contains {ooxml_pages} pages/slides/sheets, exceeding "
                    f"the maximum of {page_limit}."
                )
            details["document_pages"] = ooxml_pages

    if is_pdf_document(filename, mime_type, content):
        page_count = count_pdf_pages(content)
        if page_count is not None:
            if page_count > page_limit:
                raise IngestionLimitExceededError(
                    f"PDF contains {page_count} pages, exceeding the maximum of "
                    f"{page_limit}."
                )
            details["pdf_pages"] = page_count

    return details


def enforce_extracted_page_limit(page_count: int, max_document_pages: int) -> None:
    """Reject page/slide/sheet counts above the configured maximum."""
    page_limit = max(1, int(max_document_pages))
    if int(page_count) > page_limit:
        raise IngestionLimitExceededError(
            f"Document contains {int(page_count)} pages, exceeding the maximum of "
            f"{page_limit}."
        )


def truncate_utf8_text(text: str, max_bytes: int) -> tuple[str, int, bool]:
    """Truncate text to at most ``max_bytes`` UTF-8 bytes at a character boundary.

    Returns ``(stored_text, original_bytes, was_truncated)``.
    """
    limit = max(0, int(max_bytes))
    raw = (text or "").encode("utf-8")
    if len(raw) <= limit:
        return text or "", len(raw), False

    truncated = raw[:limit].decode("utf-8", errors="ignore")
    return truncated, len(raw), True


def truncate_extracted_text(extracted_doc: Any, max_bytes: int) -> dict[str, Any]:
    """Apply the text byte limit to the document text and its pages."""
    limit = max(0, int(max_bytes))
    original_bytes = len((extracted_doc.text or "").encode("utf-8"))

    stored_text, _, text_truncated = truncate_utf8_text(extracted_doc.text or "", limit)
    extracted_doc.text = stored_text

    remaining = max(0, limit - len(stored_text.encode("utf-8")))
    pages_truncated = False
    for page in extracted_doc.pages:
        page_text, _, page_truncated = truncate_utf8_text(page.text or "", remaining)
        page.text = page_text
        remaining = max(0, remaining - len(page_text.encode("utf-8")))
        pages_truncated = pages_truncated or page_truncated

    stored_bytes = len(extracted_doc.text.encode("utf-8"))
    return {
        "original_text_bytes": original_bytes,
        "stored_text_bytes": stored_bytes,
        "max_text_bytes": limit,
        "truncated": bool(text_truncated or pages_truncated),
        "pages_truncated": pages_truncated,
    }


def resolve_awaitable_sync(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Call ``func`` in the current thread and resolve an awaitable result.

    Runs inside ``asyncio.to_thread`` so async parser/OCR implementations stay
    off the event loop while keeping a single code path for sync test doubles.
    """
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result
