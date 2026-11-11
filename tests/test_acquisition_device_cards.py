"""Contracts for the configured-device cards on the acquisition page."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import zrzavy_energy_monitor as application
from zrzavy_energy_monitor_core.config.defaults import DEFAULT_CONFIG, DEVICE_TYPES
from zrzavy_energy_monitor_core.web.devices import build_device_cards


def _configured(**sections: dict[str, Any]) -> dict[str, Any]:
    """Return one canonical configuration with the given overrides."""

    config = deepcopy(DEFAULT_CONFIG)
    for key, value in sections.items():
        config[key].update(value)
    return config


def _card(devices: list[dict[str, Any]], role: str) -> dict[str, Any]:
    """Return the single card of one role."""

    matches = [card for card in devices if card["role"] == role]
    assert len(matches) == 1
    return matches[0]


def test_every_configurable_role_has_exactly_one_card() -> None:
    """Show all four device roles including the official grid meter."""

    devices = build_device_cards(deepcopy(DEFAULT_CONFIG), DEVICE_TYPES)

    assert [card["role"] for card in devices] == [
        "solakon_one",
        "grid_meter",
        "house_meter",
        "solakon_meter",
    ]
    assert all(card["pill"] == "inaktiv" for card in devices)
    assert all(card["pill_class"] == "off" for card in devices)


def test_grid_meter_card_shows_adapter_name_and_host() -> None:
    """Expose adapter, scheme and host of the configured grid meter."""

    config = _configured(
        grid_meter={
            "enabled": True,
            "adapter": "shrdzm_rest",
            "source_id": "grid_meter_primary",
            "name": "EVN",
            "host": "192.0.2.10",
            "port": 8080,
            "scheme": "http",
        }
    )

    card = _card(build_device_cards(config, DEVICE_TYPES), "grid_meter")

    assert card["title"] == "EVN"
    assert card["source_id"] == "grid_meter_primary"
    assert card["transport"] == "SHRDZM REST · HTTP · Port 8080"
    assert card["host"] == "192.0.2.10"
    assert card["pill"] == "aktiv"
    assert card["pill_class"] == "on"


def test_enabled_device_without_host_is_marked_as_incomplete() -> None:
    """Distinguish an enabled but unreachable configuration from an inactive one."""

    config = _configured(grid_meter={"enabled": True, "host": ""})

    card = _card(build_device_cards(config, DEVICE_TYPES), "grid_meter")

    assert card["pill"] == "Host fehlt"
    assert card["pill_class"] == "warn"
    assert card["host"] == "Keine IP konfiguriert"


def test_plant_meter_replaces_the_shelly_generation_card() -> None:
    """Show the plant meter when it takes over generation measurement."""

    config = _configured(
        plant_meter={
            "enabled": True,
            "type": "shelly_plug_m_gen3",
            "host": "192.0.2.30",
        },
        solakon_meter={"enabled": True, "host": "192.0.2.20"},
    )

    card = _card(build_device_cards(config, DEVICE_TYPES), "plant_meter")

    assert card["title"] == "Erzeugungsmessung (Anlagenzähler)"
    assert card["source_id"] == "solakon_meter"
    assert card["transport"] == DEVICE_TYPES["shelly_plug_m_gen3"]
    assert card["pill"] == "aktiv"


def test_solakon_one_simulation_is_reported_as_simulation() -> None:
    """Keep the simulation hint of the Solakon ONE card."""

    config = _configured(solakon_one={"enabled": True, "simulation": True, "host": ""})

    card = _card(build_device_cards(config, DEVICE_TYPES), "solakon_one")

    assert card["pill"] == "Simulation"
    assert card["host"] == "Simulation"
    assert card["pill_class"] == "on"


def test_acquisition_page_renders_the_grid_meter_card() -> None:
    """Render the card loop instead of the former hardcoded cards."""

    client = application.app.test_client()

    response = client.get("/acquisition")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for role in ("solakon_one", "grid_meter", "house_meter", "solakon_meter"):
        assert f'data-device-role="{role}"' in html
    assert "Konfigurierte Geräte" in html
    assert "Offizieller Netzstromzähler" in html
