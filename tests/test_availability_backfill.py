"""Contracts for deriving availability counters from existing samples."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from zrzavy_energy_monitor_core.models.device import (
    DeviceConnectionStatus,
    DeviceSnapshot,
)
from zrzavy_energy_monitor_core.persistence.availability_backfill import (
    backfill_availability,
)
from zrzavy_energy_monitor_core.persistence.database import Database
from zrzavy_energy_monitor_core.persistence.migrations import apply_migrations

APPLIED_AT = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
BASE_EPOCH = 1762826400.0  # 2026-11-11T02:00:00Z


def _database(tmp_path: Path) -> Database:
    """Return a database migrated to the current target schema."""

    database = Database(tmp_path / "backfill.db")
    with database.connect() as connection:
        apply_migrations(
            connection,
            application_version="4.11.0",
            applied_at=APPLIED_AT,
        )
    return database


def _sample(epoch: float) -> dict[str, Any]:
    """Return one minimal aggregate sample."""

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
        "solakon_ok": 1,
    }


def _grid_snapshot(status: DeviceConnectionStatus) -> DeviceSnapshot:
    """Return one grid-meter snapshot."""

    return DeviceSnapshot(
        source_id="grid_meter_primary",
        status=status,
        measurements=(),
        received_at=datetime.fromtimestamp(BASE_EPOCH + 5, timezone.utc),
    )


def test_dry_run_counts_without_writing(tmp_path: Path) -> None:
    """Count derivable rows and roll them back."""

    database = _database(tmp_path)
    database.insert_sample_with_snapshots(
        _sample(BASE_EPOCH + 5),
        grid_meter_snapshot=_grid_snapshot(DeviceConnectionStatus.ONLINE),
        availability_snapshots=(),
    )

    result = backfill_availability(
        database.path,
        start_epoch=BASE_EPOCH,
        end_epoch=BASE_EPOCH + 3600,
        apply=False,
    )

    assert result.grid_meter_rows == 1
    assert result.flag_rows == 3
    assert result.total_rows == 4
    rows = database.availability_hours_between(
        BASE_EPOCH,
        BASE_EPOCH + 3600,
        source_ids=("grid_meter_primary",),
    )
    assert rows == []


def test_apply_writes_derived_rows_and_stays_idempotent(tmp_path: Path) -> None:
    """Store derived hours once and never duplicate them."""

    database = _database(tmp_path)
    database.insert_sample_with_snapshots(
        _sample(BASE_EPOCH + 5),
        grid_meter_snapshot=_grid_snapshot(DeviceConnectionStatus.OFFLINE),
        availability_snapshots=(),
    )

    first = backfill_availability(
        database.path,
        start_epoch=BASE_EPOCH,
        end_epoch=BASE_EPOCH + 3600,
        apply=True,
    )
    second = backfill_availability(
        database.path,
        start_epoch=BASE_EPOCH,
        end_epoch=BASE_EPOCH + 3600,
        apply=True,
    )

    assert first.grid_meter_rows == 1
    assert second.total_rows == 0
    rows = database.availability_hours_between(
        BASE_EPOCH,
        BASE_EPOCH + 3600,
        source_ids=("grid_meter_primary",),
    )
    assert len(rows) == 1
    assert rows[0]["offline_count"] == 1
    assert rows[0]["origin"] == "derived"


def test_recorded_rows_are_not_overwritten_by_derived_ones(tmp_path: Path) -> None:
    """Keep collector-recorded hours authoritative."""

    database = _database(tmp_path)
    database.insert_sample_with_snapshots(
        _sample(BASE_EPOCH + 5),
        grid_meter_snapshot=_grid_snapshot(DeviceConnectionStatus.ONLINE),
        availability_snapshots=(_grid_snapshot(DeviceConnectionStatus.ONLINE),),
    )

    backfill_availability(
        database.path,
        start_epoch=BASE_EPOCH,
        end_epoch=BASE_EPOCH + 3600,
        apply=True,
    )

    rows = database.availability_hours_between(
        BASE_EPOCH,
        BASE_EPOCH + 3600,
        source_ids=("grid_meter_primary",),
    )
    assert len(rows) == 1
    assert rows[0]["origin"] == "recorded"
    assert rows[0]["observation_count"] == 1


def test_missing_table_is_reported_instead_of_writing(tmp_path: Path) -> None:
    """Fail clearly when the database was never migrated."""

    database = Database(tmp_path / "legacy.db")

    with pytest.raises(ValueError, match="migrate the database first"):
        backfill_availability(
            database.path,
            start_epoch=BASE_EPOCH,
            end_epoch=BASE_EPOCH + 3600,
            apply=True,
        )


def test_empty_range_is_rejected(tmp_path: Path) -> None:
    """Reject an inverted range."""

    database = _database(tmp_path)

    with pytest.raises(ValueError, match="must not be empty"):
        backfill_availability(
            database.path,
            start_epoch=BASE_EPOCH,
            end_epoch=BASE_EPOCH,
            apply=False,
        )
