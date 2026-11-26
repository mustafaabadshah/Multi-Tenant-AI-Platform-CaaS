from app.assistant_runtime.markdown_normalizer import normalize_markdown


def test_normalize_markdown_empty_or_none():
    assert normalize_markdown("") == ""
    assert normalize_markdown("   ") == "   "


def test_normalize_markdown_header_spacing():
    # Header missing newline before
    raw = "Some introductory text.\n# Heading 1\nContent under heading."
    expected = "Some introductory text.\n\n# Heading 1\nContent under heading."
    assert normalize_markdown(raw) == expected

    raw_h2 = "Paragraph 1\n## Subheading\nParagraph 2"
    expected_h2 = "Paragraph 1\n\n## Subheading\nParagraph 2"
    assert normalize_markdown(raw_h2) == expected_h2


def test_normalize_markdown_list_spacing():
    raw = "Here is a list:\n- Item 1\n- Item 2\nFollowing paragraph."
    expected = "Here is a list:\n\n- Item 1\n- Item 2\n\nFollowing paragraph."
    assert normalize_markdown(raw) == expected


def test_normalize_markdown_numbered_list_spacing():
    raw = "Steps to follow:\n1. Step one\n2. Step two\nFinished!"
    expected = "Steps to follow:\n\n1. Step one\n2. Step two\n\nFinished!"
    assert normalize_markdown(raw) == expected


def test_normalize_markdown_excessive_newlines():
    raw = "Paragraph 1\n\n\n\n\nParagraph 2"
    expected = "Paragraph 1\n\nParagraph 2"
    assert normalize_markdown(raw) == expected


def test_normalize_markdown_crlf_conversion():
    raw = "Line 1\r\nLine 2\r\n"
    expected = "Line 1\nLine 2\n"
    assert normalize_markdown(raw) == expected
