"""Tests that rendered pages ask for current frontend assets."""

from __future__ import annotations

import re
from pathlib import Path

import zrzavy_energy_monitor as si
from zrzavy_energy_monitor_core.web.context import compute_asset_version

STATIC_DIRECTORY = Path(si.__file__).resolve().parent / "static"


def test_asset_version_matches_the_served_static_files() -> None:
    """The startup token is derived from the assets that are actually served."""

    assert si.ASSET_VERSION == compute_asset_version(STATIC_DIRECTORY)
    assert re.fullmatch(r"[0-9a-f]{12}", si.ASSET_VERSION)


def test_dashboard_page_requests_versioned_assets() -> None:
    """Dashboard HTML carries the token so cached files are invalidated."""

    si.app.config.update(TESTING=True)

    body = si.app.test_client().get("/").get_data(as_text=True)

    assert f"app.css?v={si.ASSET_VERSION}" in body
    assert f"dashboard.js?v={si.ASSET_VERSION}" in body


def test_update_page_requests_versioned_script() -> None:
    """The update page uses the same cache-busting token for its script."""

    si.app.config.update(TESTING=True)

    body = si.app.test_client().get("/update").get_data(as_text=True)

    assert f"update.js?v={si.ASSET_VERSION}" in body
