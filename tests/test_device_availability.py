"""Contracts for the persisted device-availability time series."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import zrzavy_energy_monitor as application
from zrzavy_energy_monitor_core.models.device import (
    DeviceConnectionStatus,
    DeviceSnapshot,
)
from zrzavy_energy_monitor_core.persistence.database import Database
from zrzavy_energy_monitor_core.persistence.migrations import (
    apply_migrations,
    get_current_version,
    get_target_version,
    verify_schema,
)
from zrzavy_energy_monitor_core.services.availability import (
    availability_window,
    build_availability_api_response,
)

VIENNA = ZoneInfo("Europe/Vienna")
APPLIED_AT = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


def _migrated_database(tmp_path: Path) -> Database:
    """Return a database at the current target schema."""

    database = Database(tmp_path / "availability.db")
    with database.connect() as connection:
        apply_migrations(
            connection,
            application_version="4.11.0",
            applied_at=APPLIED_AT,
        )
        verify_schema(connection)
    return database


def _snapshot(
    status: DeviceConnectionStatus,
    *,
    source_id: str = "grid_meter_primary",
) -> DeviceSnapshot:
    """Return one snapshot with the requested connection status."""

    received_at = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    return DeviceSnapshot(
        source_id=source_id,
        status=status,
        measurements=(),
        received_at=received_at,
    )


def _sample_row(epoch: float) -> dict[str, Any]:
    """Return the minimal aggregate sample row for one cycle."""

    return {
        "ts_epoch": epoch,
        "ts_local": datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
        "grid_import_wh": 0.0,
        "feed_in_wh": 0.0,
        "solar_wh": 0.0,
        "house_wh": 0.0,
        "self_consumption_wh": 0.0,
        "house_ok": 1,
        "solar_ok": 1,
    }


def _cycle(
    database: Database,
    epoch: float,
    statuses: dict[str, DeviceConnectionStatus],
) -> int:
    """Persist one cycle with the given per-source statuses."""

    return database.insert_sample_with_snapshots(
        _sample_row(epoch),
        availability_snapshots=tuple(
            _snapshot(status, source_id=source_id)
            for source_id, status in statuses.items()
        ),
    )


def test_target_schema_adds_the_availability_table(tmp_path: Path) -> None:
    """Migrate to version 3 and expose the hourly counter table."""

    assert get_target_version() == 3
    database = _migrated_database(tmp_path)

    with database.connect() as connection:
        assert get_current_version(connection) == 3
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(device_availability_hours)"
            ).fetchall()
        }

    assert {
        "source_id",
        "hour_start",
        "online_count",
        "degraded_count",
        "offline_count",
        "observed" if False else "observation_count",
        "origin",
    } <= columns


def test_cycles_in_one_hour_accumulate_into_one_row(tmp_path: Path) -> None:
    """Count one observation per device and cycle in the same hour."""

    database = _migrated_database(tmp_path)
    base_epoch = 1762826400.0  # 2026-11-11T02:00:00Z

    _cycle(database, base_epoch, {"grid_meter_primary": DeviceConnectionStatus.ONLINE})
    _cycle(
        database,
        base_epoch + 10,
        {"grid_meter_primary": DeviceConnectionStatus.OFFLINE},
    )
    _cycle(
        database,
        base_epoch + 20,
        {"grid_meter_primary": DeviceConnectionStatus.DEGRADED},
    )

    rows = database.availability_hours_between(
        base_epoch,
        base_epoch + 3600,
        source_ids=("grid_meter_primary",),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["online_count"] == 1
    assert row["offline_count"] == 1
    assert row["degraded_count"] == 1
    assert row["observation_count"] == 3
    assert row["origin"] == "recorded"


def test_consecutive_hours_create_separate_rows(tmp_path: Path) -> None:
    """Split observations at the hour boundary."""

    database = _migrated_database(tmp_path)
    base_epoch = 1762826400.0

    _cycle(
        database,
        base_epoch + 3500,
        {"grid_meter_primary": DeviceConnectionStatus.ONLINE},
    )
    _cycle(
        database,
        base_epoch + 3700,
        {"grid_meter_primary": DeviceConnectionStatus.ONLINE},
    )

    rows = database.availability_hours_between(
        base_epoch,
        base_epoch + 7200,
        source_ids=("grid_meter_primary",),
    )

    assert [row["hour_start"] for row in rows] == [
        int(base_epoch),
        int(base_epoch) + 3600,
    ]


def test_writes_are_skipped_without_the_table(tmp_path: Path) -> None:
    """Keep the legacy database path working before the migration."""

    database = Database(tmp_path / "legacy.db")

    _cycle(
        database, 1762826400.0, {"grid_meter_primary": DeviceConnectionStatus.ONLINE}
    )

    with database.connect() as connection:
        exists = connection.execute(
            """
            SELECT 1 FROM sqlite_schema
            WHERE type = 'table' AND name = 'device_availability_hours'
            """
        ).fetchone()

    assert exists is None


def test_day_window_uses_local_midnight_and_hourly_buckets() -> None:
    """Build 24 buckets and eight axis ticks for an ordinary day."""

    window = availability_window("day", date(2026, 11, 11), VIENNA)

    assert window.bucket_count == 24
    assert window.start.isoformat() == "2026-11-11T00:00:00+01:00"
    assert window.end.isoformat() == "2026-11-12T00:00:00+01:00"
    assert window.tick_labels[0] == "00:00"
    assert window.tick_labels[-1] == "21:00"


def test_daylight_saving_days_have_23_and_25_buckets() -> None:
    """Follow the local calendar instead of a fixed 24-hour day."""

    short_day = availability_window("day", date(2026, 3, 29), VIENNA)
    long_day = availability_window("day", date(2026, 10, 25), VIENNA)

    assert short_day.bucket_count == 23
    assert long_day.bucket_count == 25


def test_week_and_month_windows_are_local_calendar_periods() -> None:
    """Start weeks on Monday and months on the first day."""

    week = availability_window("week", date(2026, 11, 11), VIENNA)
    month = availability_window("month", date(2026, 11, 11), VIENNA)

    assert week.start.isoformat() == "2026-11-09T00:00:00+01:00"
    assert week.bucket_count == 168
    assert week.tick_labels[0] == "Mo 09.11."
    assert month.bucket_count == 720
    assert month.title == "November 2026"


def test_missing_hours_stay_empty_and_are_not_counted_as_outage(
    tmp_path: Path,
) -> None:
    """Report collector gaps as no data, not as an unreachable device."""

    database = _migrated_database(tmp_path)
    start = datetime(2026, 11, 11, 0, 0, tzinfo=VIENNA)
    observed_epoch = start.timestamp() + 5 * 3600
    _cycle(
        database,
        observed_epoch,
        {"grid_meter_primary": DeviceConnectionStatus.ONLINE},
    )

    payload = build_availability_api_response(
        database,
        [
            {
                "role": "grid_meter",
                "source_id": "grid_meter_primary",
                "title": "Netzzähler",
                "transport": "SHRDZM REST",
                "enabled": True,
                "configured": True,
            }
        ],
        "day",
        "2026-11-11",
        timezone=VIENNA,
    )

    device = payload["devices"][0]
    summary = device["summary"]
    assert device["coverage"] == "recorded"
    assert summary["hours_observed"] == 1
    assert summary["hours_in_period"] == 24
    assert summary["unreachable_pct"] == 0.0
    assert summary["reachable_pct"] == 100.0
    assert sum(sum(bucket) for bucket in device["buckets"]) == 1
    assert sum(1 for bucket in device["buckets"] if not sum(bucket)) == 23


def test_current_state_prefers_reachability_over_diagnostics(
    tmp_path: Path,
) -> None:
    """Keep a degraded-only device reachable and report a real outage."""

    database = _migrated_database(tmp_path)
    start = datetime(2026, 11, 11, 0, 0, tzinfo=VIENNA)

    for index in range(4):
        _cycle(
            database,
            start.timestamp() + (10 + index) * 3600,
            {"house_meter": DeviceConnectionStatus.DEGRADED},
        )

    payload = build_availability_api_response(
        database,
        [
            {
                "role": "house_meter",
                "source_id": "house_meter",
                "title": "Hausanschluss",
                "transport": "Shelly 3EM",
                "enabled": True,
                "configured": True,
            }
        ],
        "day",
        "2026-11-11",
        timezone=VIENNA,
    )

    summary = payload["devices"][0]["summary"]
    assert summary["state"] == "good"
    assert summary["reachable_pct"] == 100.0
    assert summary["degraded_pct"] == 100.0


def test_unconfigured_device_is_reported_without_a_series() -> None:
    """Mark a disabled device instead of pretending it has no history."""

    payload = build_availability_api_response(
        None,
        [
            {
                "role": "grid_meter",
                "source_id": "grid_meter_primary",
                "title": "Netzzähler",
                "transport": "SHRDZM REST",
                "enabled": False,
                "configured": False,
            }
        ],
        "day",
        "2026-11-11",
        timezone=VIENNA,
    )

    device = payload["devices"][0]
    assert device["configured"] is False
    assert device["coverage"] == "none"
    assert device["state"] == "nodata"
    assert sum(sum(bucket) for bucket in device["buckets"]) == 0


def test_unknown_period_falls_back_to_a_day() -> None:
    """Keep the endpoint tolerant for unsupported period values."""

    payload = build_availability_api_response(
        None,
        [],
        "quarter",
        "2026-11-11",
        timezone=VIENNA,
    )

    assert payload["period"] == "day"
    assert payload["bucket_count"] == 24


def test_availability_endpoint_returns_the_period_contract() -> None:
    """Expose the availability payload over HTTP."""

    client = application.app.test_client()

    response = client.get("/api/devices/availability?period=week")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["period"] == "week"
    assert payload["bucket_seconds"] == 3600
    assert len(payload["devices"]) == 4
    for device in payload["devices"]:
        assert len(device["buckets"]) == payload["bucket_count"]
        assert set(device["summary"]) >= {
            "coverage",
            "state",
            "observations",
            "reachable_pct",
            "unreachable_pct",
        }


@pytest.mark.parametrize("period,bucket_count", [("day", 24), ("week", 168)])
def test_bucket_series_length_matches_the_window(
    tmp_path: Path,
    period: str,
    bucket_count: int,
) -> None:
    """Return exactly one counter quad per bucket."""

    database = _migrated_database(tmp_path)
    payload = build_availability_api_response(
        database,
        [
            {
                "role": "grid_meter",
                "source_id": "grid_meter_primary",
                "title": "Netzzähler",
                "transport": "SHRDZM REST",
                "enabled": True,
                "configured": True,
            }
        ],
        period,
        "2026-11-11",
        timezone=VIENNA,
    )

    assert len(payload["devices"][0]["buckets"]) == bucket_count
    assert all(len(bucket) == 4 for bucket in payload["devices"][0]["buckets"])


def test_month_payload_stays_small_and_fast(tmp_path: Path) -> None:
    """Read a month of hourly counters for four devices within budget."""

    import time

    database = _migrated_database(tmp_path)
    start = int(datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc).timestamp())
    rows = [
        (
            source_id,
            start + hour * 3600,
            120,
            5,
            3,
            0,
            0,
            128,
            start + hour * 3600 + 5,
            start + hour * 3600 + 3595,
            "recorded",
        )
        for source_id in (
            "grid_meter_primary",
            "house_meter",
            "solakon_meter",
            "solakon_one",
        )
        for hour in range(720)
    ]
    with database.connect() as connection:
        connection.executemany(
            """
            INSERT INTO device_availability_hours (
                source_id, hour_start, online_count, degraded_count,
                offline_count, disabled_count, unknown_count,
                observation_count, first_seen_epoch, last_seen_epoch, origin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()

    devices = [
        {
            "role": source_id,
            "source_id": source_id,
            "title": source_id,
            "transport": "test",
            "enabled": True,
            "configured": True,
        }
        for source_id in (
            "grid_meter_primary",
            "house_meter",
            "solakon_meter",
            "solakon_one",
        )
    ]

    started = time.perf_counter()
    payload = build_availability_api_response(
        database,
        devices,
        "month",
        "2026-11-01",
        timezone=VIENNA,
    )
    duration = time.perf_counter() - started

    assert payload["bucket_count"] == 720
    assert all(len(device["buckets"]) == 720 for device in payload["devices"])
    assert duration < 0.5, f"month payload took {duration:.3f}s"
    assert len(str(payload)) < 400_000


def test_availability_write_cost_per_cycle_stays_bounded(tmp_path: Path) -> None:
    """Persist 200 cycles with four devices per cycle within budget."""

    import time

    database = _migrated_database(tmp_path)
    statuses = {
        "grid_meter_primary": DeviceConnectionStatus.ONLINE,
        "house_meter": DeviceConnectionStatus.DEGRADED,
        "solakon_meter": DeviceConnectionStatus.ONLINE,
        "solakon_one": DeviceConnectionStatus.ONLINE,
    }
    started = time.perf_counter()
    for index in range(200):
        _cycle(database, 1762826400.0 + index * 10, statuses)
    duration = time.perf_counter() - started

    assert duration < 5.0, f"200 cycles took {duration:.3f}s"
