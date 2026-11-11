"""Build the shared Zrzavy Energy Monitor template context.

This module preserves the existing labels, source selections, device types,
version information, and collector status exposed to HTML templates.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Final

from zrzavy_energy_monitor_core.branding import (
    LEGACY_PRODUCT_NAME,
    PRODUCT_ABBREVIATION,
    PRODUCT_DESCRIPTION,
    PRODUCT_ID,
    PRODUCT_NAME,
)

# Frontend assets whose content decides the cache-busting token.
VERSIONED_ASSETS: Final = ("app.css", "dashboard.js", "update.js")


def compute_asset_version(static_directory: Path) -> str:
    """Return a short digest over the served frontend assets.

    Browsers keep `dashboard.js` and `app.css` because their names do not change
    between releases. The templates append this digest as a query parameter so a
    deployment invalidates the cached files without a manual hard reload.
    """

    digest = hashlib.sha256()
    for name in VERSIONED_ASSETS:
        digest.update(name.encode("utf-8"))
        path = static_directory / name
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def build_template_context(
    config: dict[str, Any],
    collector_running: bool,
    app_version: str,
    asset_version: str,
    device_types: dict[str, str],
) -> dict[str, Any]:
    """build_template_context provides the public operation implemented by this component."""
    return {
        "app_version": app_version,
        "asset_version": asset_version,
        "product_name": PRODUCT_NAME,
        "product_id": PRODUCT_ID,
        "product_description": PRODUCT_DESCRIPTION,
        "product_abbreviation": PRODUCT_ABBREVIATION,
        "legacy_product_name": LEGACY_PRODUCT_NAME,
        "project_name": config["general"]["project_name"],
        "site_name": config["general"]["site_name"],
        "collector_running": collector_running,
        "device_types": device_types,
        "solar_source_types": {
            "auto": "Automatisch: Shelly AC, sonst Solakon ONE AC",
            "shelly_ac": "Shelly PM Mini Gen 3 – AC-Ausgang",
            "solakon_ac": "Solakon ONE – AC-Wirkleistung",
            "solakon_pv": "Solakon ONE – PV-Eingangsleistung (DC)",
        },
        "grid_source_types": {
            "auto": (
                "Automatisch: offizieller Netzstromzähler, sonst separate "
                "Hausmessung, sonst Solakon ONE Meter"
            ),
            "house_meter": "Fallback: separate Hausmessung (Shelly 3EM)",
            "solakon_one": "Fallback: Solakon ONE – verbundenes Meter/CT",
        },
    }
