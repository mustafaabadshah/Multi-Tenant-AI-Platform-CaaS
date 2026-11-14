"""Canonical Markdown normalization for assistant output.

Single implementation combining:
- bibliography/source-footer stripping (duplicate of the structured citation tray),
- code-fence-protected unescaping of over-cautious backslash-escaped Markdown,
- spacing normalization (blank lines before headers/lists, newline collapsing),
- CRLF conversion.

This is the module imported by ``app.assistant_runtime.context`` and used by the
assistant runtime on every persisted/streamed completion.
"""

import re

_BULLET_RE = re.compile(r"^\s*[-*+]\s+")
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+")
_HEADER_RE = re.compile(r"^#{1,6}\s+")

# Match a model-generated bibliography/citation section at the end of a response.
BIBLIOGRAPHY_PATTERN = re.compile(
    r"(?:\r?\n)+"
    r"(?:(?:\*{1,2}|#{1,4}|_{1,2}|\*\*#?)?\s*)?"
    r"(?:Verified\s+Document\s+Citations|Document\s+Citations|Citations|Sources|References|Bibliography|Works\s+Cited)"
    r"[:\s\*#_]*"
    r"(?:\r?\n)[\s\S]*$",
    re.IGNORECASE,
)


def strip_generated_bibliography(text: str) -> str:
    """Strip redundant model-generated bibliographies or source lists at the end of LLM responses.

    The platform UI automatically displays structured citation trays from verified vector metadata;
    redundant LLM-generated source footers clutter the UI and often contain broken formatting.
    """
    if not text:
        return ""
    cleaned, substitutions = BIBLIOGRAPHY_PATTERN.subn("", text)
    return cleaned.rstrip() if substitutions else cleaned


def _unescape_markdown(text: str) -> str:
    """Unescape backslash-escaped Markdown tokens outside fenced code blocks.

    Safe escapes that are intentionally preserved:
    - Sequences inside fenced code blocks (``` ... ```) are never modified.
    - True literal escapes (e.g. \\\\) are left intact.
    """
    code_fence_re = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    protected_blocks: list[str] = []
    placeholders: list[str] = []

    def _protect(m: re.Match) -> str:
        idx = len(protected_blocks)
        token = f"\x00CODE_BLOCK_{idx}\x00"
        protected_blocks.append(m.group(0))
        placeholders.append(token)
        return token

    cleaned = code_fence_re.sub(_protect, text)

    # Order matters: multi-char sequences first.
    cleaned = re.sub(r"\\\*\\\*(.*?)\\\*\\\*", r"**\1**", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\\_(.+?)\\_ ", r"_\1_ ", cleaned)
    cleaned = re.sub(r"\\_(.+?)\\_", r"_\1_", cleaned)
    cleaned = re.sub(r"\\\[(\d+)\\\]", r"[\1]", cleaned)
    cleaned = re.sub(r"\\\[(\d+)\]", r"[\1]", cleaned)
    # Single character escapes for Markdown punctuation (never unescape \\ itself).
    cleaned = re.sub(r"\\([*_#\-\.!|()\[\]`{}])", r"\1", cleaned)

    for token, block in zip(placeholders, protected_blocks):
        cleaned = cleaned.replace(token, block, 1)

    return cleaned


def _normalize_spacing(text: str) -> str:
    """Ensure consistent blank-line separation around headers and lists.

    Line-based state machine: a blank line is inserted before a header/list
    block only when the preceding line is regular text, and after a list block
    when followed by regular text. Consecutive list items are never separated.
    """
    lines = text.split("\n")
    out: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not out or out[-1] == "" or stripped == "":
            out.append(line)
            continue

        prev = out[-1]
        prev_is_header = bool(_HEADER_RE.match(prev))
        prev_is_bullet = bool(_BULLET_RE.match(prev))
        prev_is_numbered = bool(_NUMBERED_RE.match(prev))
        prev_is_list = prev_is_bullet or prev_is_numbered

        is_header = bool(_HEADER_RE.match(line))
        is_bullet = bool(_BULLET_RE.match(line))
        is_numbered = bool(_NUMBERED_RE.match(line))

        if is_header and not prev_is_header:
            out.append("")
        elif (is_bullet or is_numbered) and not prev_is_list:
            out.append("")
        elif not (is_header or is_bullet or is_numbered) and prev_is_list:
            out.append("")

        out.append(line)

    result = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", result)


def normalize_markdown(text: str) -> str:
    """Normalize model output Markdown.

    Strips redundant generated bibliography sections, unescapes erroneously
    escaped Markdown tokens (outside code fences), and normalizes spacing
    around headers and lists.
    """
    if not text:
        return ""
    if not text.strip():
        return text

    cleaned = strip_generated_bibliography(text)
    cleaned = cleaned.replace("\r\n", "\n")
    cleaned = _normalize_spacing(cleaned)
    cleaned = _unescape_markdown(cleaned)

    return cleaned
