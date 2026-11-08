"""Contracts for rendering the release notes on the update page.

The notes come from a GitHub release body, so they are untrusted text. The page
must build them as DOM nodes, never as HTML, and must not turn arbitrary URLs
into links.
"""

from __future__ import annotations

from pathlib import Path

SCRIPT_FILE = Path(__file__).resolve().parents[1] / "app" / "static" / "update.js"
TEMPLATE_FILE = (
    Path(__file__).resolve().parents[1] / "app" / "templates" / "update.html"
)


def _script() -> str:
    """Return the update page script."""

    return SCRIPT_FILE.read_text(encoding="utf-8")


def _function_block(source: str, name: str) -> str:
    """Return the body of the named function, matched by braces."""

    start = source.index(f"function {name}(")
    opening = source.index("{", start)
    depth = 1
    index = opening + 1
    while depth:
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        index += 1
    return source[start:index]


def test_the_notes_are_rendered_as_dom_nodes() -> None:
    """Release notes are built from nodes, not injected as markup."""

    block = _function_block(_script(), "renderReleaseNotes")

    assert "container.replaceChildren()" in block
    assert "document.createElement" in block
    assert "innerHTML" not in block
    assert "insertAdjacentHTML" not in block
    assert "outerHTML" not in block


def test_inline_markup_is_built_without_html() -> None:
    """Bold, code and links are created as elements with textContent."""

    block = _function_block(_script(), "appendInlineMarkup")

    assert "createTextNode" in block
    assert 'createElement("strong")' in block
    assert 'createElement("code")' in block
    assert "innerHTML" not in block
    assert "textContent" in block


def test_only_https_links_become_anchors() -> None:
    """A release body cannot inject other schemes through a Markdown link."""

    block = _function_block(_script(), "appendInlineMarkup")

    assert "https?:" in block
    assert "javascript:" not in block
    assert 'rel = "noreferrer"' in block


def test_hard_wrapped_notes_stay_in_one_list_item() -> None:
    """Indented continuation lines extend the current item instead of a new one."""

    block = _function_block(_script(), "renderReleaseNotes")

    assert "/^\\s{2,}\\S/" in block
    assert "appendInlineMarkup(item" in block


def test_the_page_offers_a_block_container_for_the_notes() -> None:
    """A pre element cannot hold headings and lists, so the page uses a div."""

    template = TEMPLATE_FILE.read_text(encoding="utf-8")

    assert '<div id="release-notes"' in template
    assert '<pre id="release-notes"' not in template


def test_a_fenced_block_keeps_its_own_lines() -> None:
    """An install snippet must not be flattened into paragraphs."""

    block = _function_block(_script(), "renderReleaseNotes")

    assert 'line.startsWith("' + "```" + '")' in block
    assert 'createElement("pre")' in block
    assert "code.textContent +=" in block
