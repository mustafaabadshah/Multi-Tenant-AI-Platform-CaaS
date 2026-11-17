"""Deterministic, CPU-friendly HTML Content Extractor for Web Intelligence (M27)."""

import html
import re
from html.parser import HTMLParser
from typing import Any


class _DOMContentExtractor(HTMLParser):
    """Deterministic HTML parser that extracts main article text, code blocks, lists, and tables.

    Strips boilerplate: <script>, <style>, <nav>, <header>, <footer>, <aside>, <form>, <noscript>, <svg>.
    """

    IGNORABLE_TAGS = frozenset({
        "script", "style", "nav", "header", "footer", "aside",
        "form", "noscript", "svg", "button", "iframe", "object",
    })

    HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title: str = ""
        self.meta_description: str = ""
        self.in_title: bool = False
        self.ignore_depth: int = 0

        # Structural buffers
        self.blocks: list[str] = []
        self.current_line: list[str] = []

        # Code block tracking
        self.in_pre: bool = False
        self.in_code: bool = False
        self.code_lang: str = ""
        self.code_buffer: list[str] = []

        # Table tracking
        self.in_table: bool = False
        self.table_rows: list[list[str]] = []
        self.current_row: list[str] = []
        self.current_cell: list[str] = []
        self.is_header_row: bool = False

        # List tracking
        self.list_stack: list[str] = []  # "ul" or "ol"
        self.list_index_stack: list[int] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        # Check meta tags
        if tag_lower == "meta":
            prop = attr_dict.get("property", "").lower()
            name = attr_dict.get("name", "").lower()
            content = attr_dict.get("content", "").strip()
            if not self.title and prop in ("og:title", "twitter:title"):
                self.title = content
            if not self.meta_description and (name == "description" or prop in ("og:description", "twitter:description")):
                self.meta_description = content

        if tag_lower in self.IGNORABLE_TAGS:
            self.ignore_depth += 1
            return

        if self.ignore_depth > 0:
            return

        if tag_lower == "title":
            self.in_title = True
            return

        # Preformatted code blocks
        if tag_lower == "pre":
            self._flush_line()
            self.in_pre = True
            self.code_buffer = []
            return

        if tag_lower == "code" and self.in_pre:
            self.in_code = True
            cls = attr_dict.get("class", "")
            match = re.search(r"(?:language|lang)-([a-zA-Z0-9_+-]+)", cls)
            if match:
                self.code_lang = match.group(1).lower()
            return

        # Headings
        if tag_lower in self.HEADING_TAGS:
            self._flush_line()
            level = self.HEADING_TAGS[tag_lower]
            self.current_line.append(f"{'#' * level} ")
            return

        # Lists
        if tag_lower == "ul":
            self._flush_line()
            self.list_stack.append("ul")
            self.list_index_stack.append(0)
            return
        if tag_lower == "ol":
            self._flush_line()
            self.list_stack.append("ol")
            self.list_index_stack.append(1)
            return
        if tag_lower == "li":
            self._flush_line()
            indent = "  " * (len(self.list_stack) - 1) if len(self.list_stack) > 1 else ""
            if self.list_stack and self.list_stack[-1] == "ol":
                idx = self.list_index_stack[-1]
                self.current_line.append(f"{indent}{idx}. ")
                self.list_index_stack[-1] = idx + 1
            else:
                self.current_line.append(f"{indent}- ")
            return

        # Tables
        if tag_lower == "table":
            self._flush_line()
            self.in_table = True
            self.table_rows = []
            return
        if tag_lower == "tr" and self.in_table:
            self.current_row = []
            return
        if tag_lower in ("th", "td") and self.in_table:
            self.current_cell = []
            if tag_lower == "th":
                self.is_header_row = True
            return

        # Line breaks
        if tag_lower == "br":
            self.current_line.append("\n")
            return
        if tag_lower == "p":
            self._flush_line()
            return

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()

        if tag_lower in self.IGNORABLE_TAGS:
            if self.ignore_depth > 0:
                self.ignore_depth -= 1
            return

        if self.ignore_depth > 0:
            return

        if tag_lower == "title":
            self.in_title = False
            return

        # Preformatted code blocks
        if tag_lower == "pre":
            self.in_pre = False
            self.in_code = False
            code_text = "".join(self.code_buffer).strip()
            if code_text:
                lang = self.code_lang or ""
                self.blocks.append(f"```{lang}\n{code_text}\n```")
            self.code_buffer = []
            self.code_lang = ""
            return

        if tag_lower == "code" and self.in_pre:
            self.in_code = False
            return

        # Headings & Paragraphs
        if tag_lower in self.HEADING_TAGS or tag_lower == "p":
            self._flush_line()
            return

        # Lists
        if tag_lower in ("ul", "ol"):
            self._flush_line()
            if self.list_stack:
                self.list_stack.pop()
            if self.list_index_stack:
                self.list_index_stack.pop()
            return
        if tag_lower == "li":
            self._flush_line()
            return

        # Tables
        if tag_lower in ("th", "td") and self.in_table:
            cell_text = "".join(self.current_cell).replace("|", "\\|").replace("\n", " ").strip()
            self.current_row.append(cell_text or " ")
            self.current_cell = []
            return
        if tag_lower == "tr" and self.in_table:
            if self.current_row:
                self.table_rows.append(self.current_row)
            self.current_row = []
            return
        if tag_lower == "table" and self.in_table:
            self._render_markdown_table()
            self.in_table = False
            self.table_rows = []
            return

    def handle_data(self, data: str):
        if self.ignore_depth > 0:
            return

        if self.in_title:
            self.title += data
            return

        if self.in_pre:
            self.code_buffer.append(data)
            return

        if self.in_table:
            self.current_cell.append(data)
            return

        self.current_line.append(data)

    def _flush_line(self):
        text = "".join(self.current_line).strip()
        if text:
            self.blocks.append(text)
        self.current_line = []

    def _render_markdown_table(self):
        if not self.table_rows:
            return

        # Determine column count
        col_count = max(len(row) for row in self.table_rows)
        if col_count == 0:
            return

        # Normalize rows to same column count
        normalized = []
        for r in self.table_rows:
            padded = r + [" "] * (col_count - len(r))
            normalized.append(padded)

        table_md_lines = []
        # Header row
        header = normalized[0]
        table_md_lines.append("| " + " | ".join(header) + " |")
        table_md_lines.append("| " + " | ".join(["---"] * col_count) + " |")

        for row in normalized[1:]:
            table_md_lines.append("| " + " | ".join(row) + " |")

        self.blocks.append("\n".join(table_md_lines))


class WebContentExtractor:
    """Extracts clean, readable, structured Markdown from raw HTML."""

    MAX_EXTRACTED_CHARS = 30000

    @classmethod
    def extract(cls, raw_html: str, source_url: str = "") -> dict[str, Any]:
        """Extract main content, title, and metadata from an HTML string."""
        if not raw_html or not raw_html.strip():
            return {
                "title": "",
                "description": "",
                "content": "",
                "status": "EMPTY",
                "char_count": 0,
                "is_js_required": False,
                "is_blocked": False,
            }

        # 1. Quick check for common bot/JS challenges
        raw_lower = raw_html.lower()
        is_js_required = bool(
            "please enable javascript" in raw_lower
            or "you need to enable javascript" in raw_lower
            or "enable javascript to run this app" in raw_lower
        )
        is_blocked = bool(
            "attention required! | cloudflare" in raw_lower
            or "just a moment..." in raw_lower
            or "cf-browser-verification" in raw_lower
            or "captcha challenge" in raw_lower
            or "403 forbidden" in raw_lower
            or "access denied" in raw_lower and len(raw_html) < 2000
        )

        parser = _DOMContentExtractor()
        try:
            parser.feed(raw_html)
            parser._flush_line()
        except Exception:
            # Fallback to plain regex stripping if parser encounters broken markup
            plain = re.sub(r"<[^>]+>", " ", raw_html)
            plain = re.sub(r"\s+", " ", plain).strip()
            return {
                "title": parser.title.strip() or "Web Document",
                "description": parser.meta_description.strip(),
                "content": plain[: cls.MAX_EXTRACTED_CHARS],
                "status": "FALLBACK_PARSED",
                "char_count": len(plain[: cls.MAX_EXTRACTED_CHARS]),
                "is_js_required": is_js_required,
                "is_blocked": is_blocked,
            }

        title = parser.title.strip()
        description = parser.meta_description.strip()

        # Deduplicate and format blocks
        joined_content = "\n\n".join(b for b in parser.blocks if b.strip())

        # Clean multiple blank lines
        joined_content = re.sub(r"\n{3,}", "\n\n", joined_content).strip()

        # Enforce bounds
        truncated = False
        if len(joined_content) > cls.MAX_EXTRACTED_CHARS:
            joined_content = joined_content[: cls.MAX_EXTRACTED_CHARS] + "\n\n[Content truncated at length limit...]"
            truncated = True

        status = "SUCCESS"
        if is_blocked:
            status = "BLOCKED"
        elif is_js_required and len(joined_content) < 500:
            status = "JS_REQUIRED"
        elif not joined_content:
            status = "EMPTY"

        return {
            "title": title or "Web Page",
            "description": description,
            "content": joined_content,
            "status": status,
            "char_count": len(joined_content),
            "is_js_required": is_js_required,
            "is_blocked": is_blocked,
            "truncated": truncated,
        }
