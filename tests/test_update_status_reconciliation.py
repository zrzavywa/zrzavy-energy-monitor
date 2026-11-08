"""Tests for reconciling the stored update status with the running version."""

from __future__ import annotations

from pathlib import Path

from zrzavy_energy_monitor_core.services.update import read_update_status_response

STORED = {
    "state": "success",
    "progress": 100,
    "message": "Update erfolgreich installiert.",
    "installed_version": "4.5.3",
    "available_version": "4.5.5",
    "archive_path": None,
    "updated_at": "2026-07-29T20:01:50+00:00",
}


def _reader(payload: dict):
    def read(path: Path) -> dict:
        return dict(payload)

    return read


def test_running_version_wins_over_stale_status(tmp_path: Path) -> None:
    status = read_update_status_response(
        tmp_path / "update-status.json",
        _reader(STORED),
        running_version="4.6.1",
    )

    assert status["installed_version"] == "4.6.1"
    assert status["status_installed_version"] == "4.5.3"
    assert status["available_version"] == "4.5.5"
    assert status["state"] == "success"
    # The stored record cannot describe the running installation.
    assert status["status_is_historic"] is True


def test_matching_version_stays_untouched(tmp_path: Path) -> None:
    stored = dict(STORED, installed_version="4.6.1")

    status = read_update_status_response(
        tmp_path / "update-status.json",
        _reader(stored),
        running_version="4.6.1",
    )

    assert status["installed_version"] == "4.6.1"
    assert "status_installed_version" not in status
    assert status["status_is_historic"] is False


def test_without_a_running_version_the_file_is_returned_as_is(
    tmp_path: Path,
) -> None:
    status = read_update_status_response(
        tmp_path / "update-status.json",
        _reader(STORED),
    )

    assert status["installed_version"] == "4.5.3"
    assert "status_installed_version" not in status
    assert "status_is_historic" not in status
