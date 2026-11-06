"""JSON Document Parser using Python standard library."""

import json
import time
from typing import Any

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
)


def flatten_json_to_paths(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten nested JSON into a list of (key_path, value) tuples."""
    items: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_prefix = f"{prefix}.{k}" if prefix else str(k)
            items.extend(flatten_json_to_paths(v, new_prefix))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            new_prefix = f"{prefix}[{idx}]"
            items.extend(flatten_json_to_paths(item, new_prefix))
    else:
        items.append((prefix, obj))
    return items


class JSONParser(DocumentParser):
    """Secure JSON document parser with key-path extraction and structured formatting."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".json", ".jsonl"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {"application/json", "application/x-ndjson", "text/json"}

    @property
    def parser_name(self) -> str:
        return "python-json_Parser"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate if content is valid JSON or JSONL."""
        stripped = content.strip()
        if stripped.startswith((b"{", b"[")):
            return True
        return False

    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        start_time = time.perf_counter()
        warnings: list[str] = []

        decoded_text = content.decode("utf-8", errors="replace")
        parsed_data: Any = None
        is_jsonl = False

        try:
            parsed_data = json.loads(decoded_text)
        except json.JSONDecodeError:
            # Try parsing as JSON Lines (JSONL)
            jsonl_items = []
            for line_idx, line in enumerate(decoded_text.splitlines()):
                line_str = line.strip()
                if line_str:
                    try:
                        jsonl_items.append(json.loads(line_str))
                    except json.JSONDecodeError:
                        warnings.append(f"Line {line_idx+1} could not be parsed as JSON.")
            if jsonl_items:
                parsed_data = jsonl_items
                is_jsonl = True
            else:
                raise ValueError("Content is not valid JSON or JSON Lines.")

        pretty_text = json.dumps(parsed_data, indent=2, ensure_ascii=False)
        flat_paths = flatten_json_to_paths(parsed_data)

        # Generate readable path breakdown for search and chunking
        path_summary_lines = ["### Key-Value Attributes:\n"]
        for path, val in flat_paths[:500]:  # Limit paths summary
            path_summary_lines.append(f"- **{path}**: `{val}`")

        full_content = (
            f"# JSON Document: {filename}\n\n"
            + "\n".join(path_summary_lines)
            + "\n\n### Full Data:\n```json\n"
            + pretty_text[:100000]  # Cap snippet to 100KB in raw display
            + "\n```"
        )

        sections = [
            ExtractedSection(
                heading=f"JSON Structure: {filename}",
                level=1,
                content=full_content,
                page_number=1,
            )
        ]

        page = ExtractedPage(
            page_number=1,
            text=full_content,
            metadata={"is_jsonl": is_jsonl, "paths_count": len(flat_paths)},
        )

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "application/json",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            title=filename,
            text=full_content,
            pages=[page],
            sections=sections,
            metadata={
                "is_jsonl": is_jsonl,
                "data_type": type(parsed_data).__name__,
                "total_paths": len(flat_paths),
            },
            warnings=warnings,
            extraction_stats={
                "duration_ms": duration_ms,
                "paths_count": len(flat_paths),
                "char_count": len(full_content),
            },
        )
