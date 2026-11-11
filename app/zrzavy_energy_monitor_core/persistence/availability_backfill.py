"""Derive hourly availability counters from the already persisted samples.

The collector records availability from now on. Existing detail rows already
carry a device status per cycle, so the history can be reconstructed once.
Derived hours are marked with origin = 'derived' and never overwrite recorded
hours.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Final

HOUR_SECONDS: Final = 3600
DAY_SECONDS: Final = 86_400

GRID_METER_BACKFILL_SQL: Final = """
    INSERT INTO device_availability_hours (
        source_id, hour_start, online_count, degraded_count, offline_count,
        disabled_count, unknown_count, observation_count,
        first_seen_epoch, last_seen_epoch, origin
    )
    SELECT grid_meter_samples.source_id,
           CAST(samples.ts_epoch / ? AS INTEGER) * ? AS hour_start,
           SUM(CASE WHEN grid_meter_samples.device_status = 'online'
                    THEN 1 ELSE 0 END),
           SUM(CASE WHEN grid_meter_samples.device_status = 'degraded'
                    THEN 1 ELSE 0 END),
           SUM(CASE WHEN grid_meter_samples.device_status = 'offline'
                    THEN 1 ELSE 0 END),
           SUM(CASE WHEN grid_meter_samples.device_status = 'disabled'
                    THEN 1 ELSE 0 END),
           SUM(CASE WHEN grid_meter_samples.device_status NOT IN
                        ('online', 'degraded', 'offline', 'disabled')
                    THEN 1 ELSE 0 END),
           COUNT(*),
           MIN(samples.ts_epoch),
           MAX(samples.ts_epoch),
           'derived'
    FROM grid_meter_samples
    JOIN samples ON samples.id = grid_meter_samples.sample_id
    WHERE samples.ts_epoch >= ? AND samples.ts_epoch < ?
    GROUP BY grid_meter_samples.source_id, hour_start
    ON CONFLICT (source_id, hour_start) DO NOTHING
"""

PHASE_BACKFILL_SQL: Final = """
    INSERT INTO device_availability_hours (
        source_id, hour_start, online_count, degraded_count, offline_count,
        disabled_count, unknown_count, observation_count,
        first_seen_epoch, last_seen_epoch, origin
    )
    SELECT phase_samples.source_id,
           CAST(samples.ts_epoch / ? AS INTEGER) * ? AS hour_start,
           SUM(CASE WHEN phase_samples.device_status = 'online' THEN 1 ELSE 0 END),
           SUM(CASE WHEN phase_samples.device_status = 'degraded' THEN 1 ELSE 0 END),
           SUM(CASE WHEN phase_samples.device_status = 'offline' THEN 1 ELSE 0 END),
           SUM(CASE WHEN phase_samples.device_status = 'disabled' THEN 1 ELSE 0 END),
           SUM(CASE WHEN phase_samples.device_status NOT IN
                        ('online', 'degraded', 'offline', 'disabled')
                    THEN 1 ELSE 0 END),
           COUNT(*),
           MIN(samples.ts_epoch),
           MAX(samples.ts_epoch),
           'derived'
    FROM phase_samples
    JOIN samples ON samples.id = phase_samples.sample_id
    WHERE samples.ts_epoch >= ? AND samples.ts_epoch < ?
    GROUP BY phase_samples.source_id, hour_start
    ON CONFLICT (source_id, hour_start) DO NOTHING
"""

FLAG_BACKFILL_SQL: Final = """
    INSERT INTO device_availability_hours (
        source_id, hour_start, online_count, degraded_count, offline_count,
        disabled_count, unknown_count, observation_count,
        first_seen_epoch, last_seen_epoch, origin
    )
    SELECT ?, CAST(ts_epoch / ? AS INTEGER) * ? AS hour_start,
           SUM(CASE WHEN {column} = 1 THEN 1 ELSE 0 END),
           0,
           SUM(CASE WHEN {column} = 1 THEN 0 ELSE 1 END),
           0, 0,
           COUNT(*),
           MIN(ts_epoch),
           MAX(ts_epoch),
           'derived'
    FROM samples
    WHERE ts_epoch >= ? AND ts_epoch < ?
    GROUP BY hour_start
    ON CONFLICT (source_id, hour_start) DO NOTHING
"""

FLAG_SOURCES: Final[tuple[tuple[str, str], ...]] = (
    ("house_meter", "house_ok"),
    ("solakon_meter", "solar_ok"),
    ("solakon_one", "solakon_ok"),
)


@dataclass(frozen=True)
class BackfillResult:
    """Report derived availability rows for one time range."""

    grid_meter_rows: int
    house_phase_rows: int
    flag_rows: int

    @property
    def total_rows(self) -> int:
        """Return all newly derived rows."""

        return self.grid_meter_rows + self.house_phase_rows + self.flag_rows


def backfill_availability(
    database_path: Path,
    *,
    start_epoch: float,
    end_epoch: float,
    apply: bool,
) -> BackfillResult:
    """Derive hourly counters for one range, optionally committing them.

    Args:
        database_path: Existing application database.
        start_epoch: Inclusive lower bound of the range.
        end_epoch: Exclusive upper bound of the range.
        apply: Write the derived rows. False counts them and rolls back.

    Returns:
        Counts per source family.

    Raises:
        sqlite3.DatabaseError: If the database cannot be read or written.
        ValueError: If the range is empty or the schema lacks the table.
    """

    if end_epoch <= start_epoch:
        raise ValueError("backfill range must not be empty")

    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        if not _has_availability_table(connection):
            raise ValueError(
                "device_availability_hours is missing; migrate the database first"
            )
        connection.execute("BEGIN IMMEDIATE")
        grid_rows = connection.execute(
            GRID_METER_BACKFILL_SQL,
            (HOUR_SECONDS, HOUR_SECONDS, start_epoch, end_epoch),
        ).rowcount
        phase_rows = connection.execute(
            PHASE_BACKFILL_SQL,
            (HOUR_SECONDS, HOUR_SECONDS, start_epoch, end_epoch),
        ).rowcount
        flag_rows = 0
        for source_id, column in FLAG_SOURCES:
            flag_rows += connection.execute(
                FLAG_BACKFILL_SQL.format(column=column),
                (
                    source_id,
                    HOUR_SECONDS,
                    HOUR_SECONDS,
                    start_epoch,
                    end_epoch,
                ),
            ).rowcount
        if apply:
            connection.commit()
        else:
            connection.rollback()
        return BackfillResult(
            grid_meter_rows=max(0, grid_rows),
            house_phase_rows=max(0, phase_rows),
            flag_rows=max(0, flag_rows),
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _has_availability_table(connection: sqlite3.Connection) -> bool:
    """Return whether the availability table exists."""

    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_schema
        WHERE type = 'table' AND name = 'device_availability_hours'
        """
    ).fetchone()
    return row is not None
