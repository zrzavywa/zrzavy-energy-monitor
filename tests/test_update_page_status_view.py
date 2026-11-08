"""Contracts for the update page download status panel.

The panel used to report the stored update status verbatim. A release installed
without the privileged updater left a record behind that named another version,
and the page presented it as the outcome of the running installation. These
tests pin the separation between a current and a historic record.
"""

from __future__ import annotations

from pathlib import Path

SCRIPT_FILE = Path(__file__).resolve().parents[1] / "app" / "static" / "update.js"


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


def test_the_view_is_built_from_the_api_flag() -> None:
    """The historic marker comes from the API, not from string guessing."""

    block = _function_block(_script(), "buildDownloadStatusView")

    assert "payload.status_is_historic" in block
    assert "älterer Vorgang" in block
    assert "stammt nicht aus diesem Vorgang" in block


def test_a_historic_record_never_claims_a_successful_install() -> None:
    """The success sentence must stay in the branch for current records."""

    block = _function_block(_script(), "buildDownloadStatusView")
    current_branch = block.split("const when = formatStatusTime")[0]
    historic_branch = block[len(current_branch) :]

    assert "wurde erfolgreich installiert" in current_branch
    assert "wurde erfolgreich installiert" not in historic_branch
    assert "result: null" in historic_branch


def test_the_renderer_uses_the_view_model_only() -> None:
    """The renderer must not build its own wording or its own decision."""

    block = _function_block(_script(), "renderDownloadStatus")

    assert "buildDownloadStatusView(payload)" in block
    assert "view.result" in block
    assert "view.verifiedVersion" in block
    assert "wurde erfolgreich installiert" not in block


def test_a_historic_record_cannot_be_installed_again() -> None:
    """The install button stays disabled while a historic record is shown."""

    block = _function_block(_script(), "renderDownloadStatus")

    assert "!view.historic" in block
