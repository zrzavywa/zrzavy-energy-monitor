"""Tests for the monthly phase aggregation used by the year view."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from zrzavy_energy_monitor_core.persistence.database import Database


def _insert_sample(
    connection: sqlite3.Connection,
    ts_epoch: float,
    ts_local: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO samples (ts_epoch, ts_local)
        VALUES (?, ?)
        """,
        (ts_epoch, ts_local),
    )
    return int(cursor.lastrowid or 0)


def _insert_phase_row(
    connection: sqlite3.Connection,
    sample_id: int,
    *,
    l1_power_w: float,
    quality: str = "reported",
    spread_w: float | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO phase_samples (
            sample_id, source_id, measurement_role, device_status,
            measured_at, received_at, l1_power_w, l1_quality,
            phase_power_spread_w
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_id,
            "house_meter",
            "house_total",
            "online",
            f"measured-{sample_id}",
            f"received-{sample_id}",
            l1_power_w,
            quality,
            spread_w,
        ),
    )


def test_phase_month_aggregation_groups_local_calendar_months(
    tmp_path: Path,
) -> None:
    """Rows are grouped by the stored local month and summed per phase."""

    database = Database(tmp_path / "phase-month.db")
    with database.connect() as connection:
        july_one = _insert_sample(
            connection, 1_774_000_000.0, "2026-07-24T10:00:00+02:00"
        )
        july_two = _insert_sample(
            connection, 1_774_003_600.0, "2026-07-24T11:00:00+02:00"
        )
        august = _insert_sample(
            connection, 1_774_500_000.0, "2026-08-03T09:00:00+02:00"
        )
        _insert_phase_row(connection, july_one, l1_power_w=100.0, spread_w=5.0)
        _insert_phase_row(connection, july_two, l1_power_w=200.0, spread_w=9.0)
        _insert_phase_row(connection, august, l1_power_w=300.0, quality="suspect")
        connection.commit()

    rows = database.aggregate_phase_by_month(
        1_773_000_000.0,
        1_776_000_000.0,
    )

    assert [row["month_start"] for row in rows] == ["2026-07", "2026-08"]
    july, august_row = rows
    assert july["sample_count"] == 2
    assert july["l1_power_sum"] == 300.0
    assert july["l1_power_count"] == 2
    assert july["max_spread_w"] == 9.0
    assert july["suspect_sample_count"] == 0
    assert august_row["sample_count"] == 1
    assert august_row["l1_power_sum"] == 300.0
    assert august_row["suspect_sample_count"] == 1


def test_phase_month_aggregation_respects_the_source_and_range(
    tmp_path: Path,
) -> None:
    """Other sources and rows outside the range stay out of the buckets."""

    database = Database(tmp_path / "phase-month-range.db")
    with database.connect() as connection:
        inside = _insert_sample(
            connection, 1_774_000_000.0, "2026-07-24T10:00:00+02:00"
        )
        outside = _insert_sample(
            connection, 1_700_000_000.0, "2023-11-14T22:13:20+01:00"
        )
        _insert_phase_row(connection, inside, l1_power_w=50.0)
        connection.execute(
            """
            UPDATE phase_samples SET source_id = 'other_meter'
            WHERE sample_id = ?
            """,
            (outside,),
        )
        connection.commit()

    rows = database.aggregate_phase_by_month(
        1_773_000_000.0,
        1_776_000_000.0,
    )

    assert len(rows) == 1
    assert rows[0]["month_start"] == "2026-07"
    assert rows[0]["sample_count"] == 1
