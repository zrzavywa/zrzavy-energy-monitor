"""Tests for the raw-data retention planning and deletion helpers."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from zrzavy_energy_monitor_core.persistence.database import Database
from zrzavy_energy_monitor_core.persistence.maintenance import (
    DatabaseMaintenanceError,
    apply_retention,
    plan_retention,
)

NOW = 1_800_000_000.0
DAY = 86_400.0


def _prepare(path: Path) -> Database:
    database = Database(path)
    database.initialize()
    return database


def _insert_sample(connection: sqlite3.Connection, ts_epoch: float) -> int:
    cursor = connection.execute(
        "INSERT INTO samples (ts_epoch, ts_local) VALUES (?, ?)",
        (ts_epoch, "2027-01-01T00:00:00+00:00"),
    )
    return int(cursor.lastrowid or 0)


def _insert_phase(connection: sqlite3.Connection, sample_id: int) -> None:
    connection.execute(
        """
        INSERT INTO phase_samples (
            sample_id, source_id, measurement_role, device_status,
            measured_at, received_at, l1_power_w
        ) VALUES (?, 'house_meter', 'house_total', 'online', ?, ?, 1.0)
        """,
        (sample_id, "2027-01-01T00:00:00+00:00", "2027-01-01T00:00:01+00:00"),
    )


def _seed(path: Path, *, with_recent: bool) -> tuple[int, int | None]:
    with closing(sqlite3.connect(path)) as connection:
        old_id = _insert_sample(connection, NOW - 900 * DAY)
        _insert_phase(connection, old_id)
        recent_id: int | None = None
        if with_recent:
            recent_id = _insert_sample(connection, NOW - 10 * DAY)
            _insert_phase(connection, recent_id)
        connection.commit()
    return old_id, recent_id


def test_plan_counts_only_rows_older_than_the_cutoff(tmp_path: Path) -> None:
    path = tmp_path / "retention.db"
    _prepare(path)
    _seed(path, with_recent=True)

    plan = plan_retention(path, keep_raw_days=730, now_epoch=NOW)

    assert plan.sample_count == 1
    assert plan.dependent_counts.get("phase_samples") == 1
    assert plan.keep_raw_days == 730
    assert plan.cutoff_epoch == pytest.approx(NOW - 730 * DAY)


def test_plan_changes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "retention.db"
    _prepare(path)
    _seed(path, with_recent=False)

    plan_retention(path, keep_raw_days=730, now_epoch=NOW)

    with closing(sqlite3.connect(path)) as connection:
        remaining = connection.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    assert remaining == 1


def test_apply_deletes_old_rows_and_keeps_recent_ones(tmp_path: Path) -> None:
    path = tmp_path / "retention.db"
    _prepare(path)
    _, recent_id = _seed(path, with_recent=True)

    plan = plan_retention(path, keep_raw_days=730, now_epoch=NOW)
    result = apply_retention(path, plan)

    assert result.deleted_samples == 1
    assert result.deleted_dependent_counts.get("phase_samples") == 1
    with closing(sqlite3.connect(path)) as connection:
        sample_ids = {row[0] for row in connection.execute("SELECT id FROM samples")}
        phase_ids = {
            row[0] for row in connection.execute("SELECT sample_id FROM phase_samples")
        }
    assert sample_ids == {recent_id}
    assert phase_ids == {recent_id}


def test_apply_with_nothing_to_delete_is_a_noop(tmp_path: Path) -> None:
    path = tmp_path / "retention.db"
    _prepare(path)
    with closing(sqlite3.connect(path)) as connection:
        _insert_sample(connection, NOW - 10 * DAY)
        connection.commit()

    plan = plan_retention(path, keep_raw_days=730, now_epoch=NOW)
    result = apply_retention(path, plan)

    assert plan.sample_count == 0
    assert result.deleted_samples == 0
    assert result.deleted_dependent_counts == {}


def test_plan_rejects_non_positive_window(tmp_path: Path) -> None:
    path = tmp_path / "retention.db"
    _prepare(path)

    with pytest.raises(DatabaseMaintenanceError):
        plan_retention(path, keep_raw_days=0, now_epoch=NOW)


def test_apply_rejects_a_plan_for_another_database(tmp_path: Path) -> None:
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    _prepare(first)
    _prepare(second)
    _seed(first, with_recent=False)

    plan = plan_retention(first, keep_raw_days=730, now_epoch=NOW)

    with pytest.raises(DatabaseMaintenanceError):
        apply_retention(second, plan)
