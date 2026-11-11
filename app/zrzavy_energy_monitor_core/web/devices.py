"""Build the configured-device cards of the acquisition page.

The cards derive from the active configuration so that a newly configured or
newly disabled source appears without a template change. This module is
presentation only: it does not read devices, change measurement semantics, or
touch persistence.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

ROLE_SOLAKON_ONE: Final = "solakon_one"
ROLE_GRID_METER: Final = "grid_meter"
ROLE_HOUSE_METER: Final = "house_meter"
ROLE_PLANT_METER: Final = "plant_meter"
ROLE_SOLAKON_METER: Final = "solakon_meter"

GRID_METER_ADAPTER_LABELS: Final[dict[str, str]] = {
    "tasmota_http": "Tasmota HTTP",
    "shrdzm_rest": "SHRDZM REST",
}

NO_HOST: Final = "Keine IP konfiguriert"
NO_ADAPTER: Final = "Adapter nicht konfiguriert"
NO_DEVICE_TYPE: Final = "Gerätetyp nicht konfiguriert"


def build_device_cards(
    config: Mapping[str, Any],
    device_types: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Return one presentation record per configured device role.

    Args:
        config: Active application configuration.
        device_types: Human-readable Shelly device type labels.

    Returns:
        Cards in display order: Solakon ONE, grid meter, house meter,
        generation meter. Each card carries its role, stable source
        identifier, title, icon, transport description, host display,
        enabled flag, and the status pill text and CSS modifier.
    """

    plant_meter = _section(config, ROLE_PLANT_METER)
    solar_role = ROLE_PLANT_METER if plant_meter.get("enabled") else ROLE_SOLAKON_METER
    solar_config = (
        plant_meter
        if plant_meter.get("enabled")
        else _section(config, ROLE_SOLAKON_METER)
    )

    return [
        _solakon_one_card(_section(config, ROLE_SOLAKON_ONE)),
        _grid_meter_card(_section(config, ROLE_GRID_METER)),
        _shelly_card(
            _section(config, ROLE_HOUSE_METER),
            device_types,
            role=ROLE_HOUSE_METER,
            source_id=ROLE_HOUSE_METER,
            icon="H",
            title="Separate Hausanschlussmessung",
        ),
        _shelly_card(
            solar_config,
            device_types,
            role=solar_role,
            # The collector stores every generation source under this stable
            # identifier, including the plant-meter variant.
            source_id=ROLE_SOLAKON_METER,
            icon="S",
            title=(
                "Erzeugungsmessung (Anlagenzähler)"
                if solar_role == ROLE_PLANT_METER
                else "Shelly AC-Erzeugungsmessung"
            ),
        ),
    ]


def _solakon_one_card(device: Mapping[str, Any]) -> dict[str, Any]:
    """Return the Solakon ONE card."""

    enabled = bool(device.get("enabled"))
    simulation = bool(device.get("simulation"))
    host = _text(device.get("host"))
    port = device.get("port", "–")
    device_id = device.get("device_id", "–")
    configured = bool(host) or simulation

    return {
        "role": ROLE_SOLAKON_ONE,
        "source_id": ROLE_SOLAKON_ONE,
        "title": "Solakon ONE",
        "icon": "1",
        "transport": f"Modbus TCP · Port {port} · Geräte-ID {device_id}",
        "host": "Simulation" if simulation else (host or NO_HOST),
        "enabled": enabled,
        "configured": configured,
        "pill": "Simulation"
        if enabled and simulation
        else _pill_text(enabled, configured),
        "pill_class": _pill_class(enabled, configured),
    }


def _grid_meter_card(device: Mapping[str, Any]) -> dict[str, Any]:
    """Return the official grid-meter card."""

    enabled = bool(device.get("enabled"))
    adapter = _text(device.get("adapter"))
    scheme = _text(device.get("scheme")) or "http"
    host = _text(device.get("host"))
    port = device.get("port", "–")
    configured = bool(host)

    return {
        "role": ROLE_GRID_METER,
        "source_id": _text(device.get("source_id")) or "grid_meter_primary",
        "title": _text(device.get("name")) or "Offizieller Netzstromzähler",
        "icon": "N",
        "transport": (
            f"{GRID_METER_ADAPTER_LABELS.get(adapter, adapter or NO_ADAPTER)}"
            f" · {scheme.upper()} · Port {port}"
        ),
        "host": host or NO_HOST,
        "enabled": enabled,
        "configured": configured,
        "pill": _pill_text(enabled, configured),
        "pill_class": _pill_class(enabled, configured),
    }


def _shelly_card(
    device: Mapping[str, Any],
    device_types: Mapping[str, str],
    *,
    role: str,
    source_id: str,
    icon: str,
    title: str,
) -> dict[str, Any]:
    """Return one Shelly-based device card."""

    enabled = bool(device.get("enabled"))
    device_type = _text(device.get("type"))
    host = _text(device.get("host"))
    configured = bool(host)

    return {
        "role": role,
        "source_id": source_id,
        "title": title,
        "icon": icon,
        "transport": device_types.get(device_type) or device_type or NO_DEVICE_TYPE,
        "host": host or NO_HOST,
        "enabled": enabled,
        "configured": configured,
        "pill": _pill_text(enabled, configured),
        "pill_class": _pill_class(enabled, configured),
    }


def _pill_text(enabled: bool, configured: bool) -> str:
    """Return the short status label of a card."""

    if not enabled:
        return "inaktiv"
    return "aktiv" if configured else "Host fehlt"


def _pill_class(enabled: bool, configured: bool) -> str:
    """Return the CSS modifier of a card status pill."""

    if not enabled:
        return "off"
    return "on" if configured else "warn"


def _section(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Return one configuration section or an empty mapping."""

    value = config.get(key)
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    """Return trimmed text for an optional configuration value."""

    return "" if value is None else str(value).strip()
