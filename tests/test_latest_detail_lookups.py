"""Tests for the bounded latest-detail lookups and asset versioning."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from zrzavy_energy_monitor_core.persistence.database import (
    LATEST_ENERGY_BALANCE_SQL,
    LATEST_GRID_METER_SQL,
    LATEST_PHASE_SQL,
    LATEST_SAMPLE_WINDOW,
    Database,
)
from zrzavy_energy_monitor_core.web.context import compute_asset_version


def _insert_sample(
    connection: sqlite3.Connection,
    ts_epoch: float,
    *,
    grid_source: str | None = None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO samples (ts_epoch, ts_local, grid_source)
        VALUES (?, ?, ?)
        """,
        (ts_epoch, f"sample-{ts_epoch}", grid_source),
    )
    return int(cursor.lastrowid or 0)


def _insert_grid_meter_row(
    connection: sqlite3.Connection,
    sample_id: int,
    *,
    source_id: str = "grid_meter_primary",
    grid_power_w: float = -1.0,
) -> None:
    connection.execute(
        """
        INSERT INTO grid_meter_samples (
            sample_id, source_id, source_name, adapter, device_status,
            measured_at, received_at, grid_power_w
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_id,
            source_id,
            source_id,
            "bench",
            "online",
            f"measured-{sample_id}",
            f"received-{sample_id}",
            grid_power_w,
        ),
    )


def _insert_phase_row(
    connection: sqlite3.Connection,
    sample_id: int,
    *,
    source_id: str = "house_meter",
    l1_power_w: float = 1.0,
) -> None:
    connection.execute(
        """
        INSERT INTO phase_samples (
            sample_id, source_id, measurement_role, device_status,
            measured_at, received_at, l1_power_w
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_id,
            source_id,
            "house_total",
            "online",
            f"measured-{sample_id}",
            f"received-{sample_id}",
            l1_power_w,
        ),
    )


def _insert_balance_row(
    connection: sqlite3.Connection,
    sample_id: int,
    *,
    house_power_w: float = 2.0,
) -> None:
    connection.execute(
        """
        INSERT INTO energy_balance_samples (
            sample_id, calculated_at, quality, house_power_w
        ) VALUES (?, ?, ?, ?)
        """,
        (sample_id, f"calculated-{sample_id}", "valid", house_power_w),
    )


def _plan(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[object, ...],
) -> str:
    rows = connection.execute(f"EXPLAIN QUERY PLAN {sql}", parameters).fetchall()
    return "\n".join(str(row["detail"]) for row in rows)


def test_latest_grid_meter_sample_returns_newest_timestamp(tmp_path: Path) -> None:
    """The newest timestamp wins even when it was inserted first."""

    database = Database(tmp_path / "grid.db")
    with database.connect() as connection:
        newest = _insert_sample(connection, 300.0, grid_source="primary")
        older = _insert_sample(connection, 100.0, grid_source="primary")
        _insert_grid_meter_row(connection, newest, grid_power_w=-300.0)
        _insert_grid_meter_row(connection, older, grid_power_w=-100.0)
        connection.commit()

    row = database.latest_grid_meter_sample()

    assert row is not None
    assert row["ts_epoch"] == 300.0
    assert row["grid_power_w"] == -300.0


def test_latest_grid_meter_sample_ignores_other_sources(tmp_path: Path) -> None:
    """Only rows of the requested source are candidates."""

    database = Database(tmp_path / "grid-source.db")
    with database.connect() as connection:
        newest = _insert_sample(connection, 300.0)
        older = _insert_sample(connection, 100.0)
        _insert_grid_meter_row(connection, newest, source_id="other_meter")
        _insert_grid_meter_row(connection, older, grid_power_w=-42.0)
        connection.commit()

    row = database.latest_grid_meter_sample()

    assert row is not None
    assert row["source_id"] == "grid_meter_primary"
    assert row["ts_epoch"] == 100.0


def test_latest_phase_and_balance_samples_return_newest_row(tmp_path: Path) -> None:
    """Phase and energy-balance lookups also pick the newest timestamp."""

    database = Database(tmp_path / "detail.db")
    with database.connect() as connection:
        newest = _insert_sample(connection, 500.0)
        older = _insert_sample(connection, 200.0)
        _insert_phase_row(connection, newest, l1_power_w=111.0)
        _insert_phase_row(connection, older, l1_power_w=222.0)
        _insert_balance_row(connection, newest, house_power_w=333.0)
        _insert_balance_row(connection, older, house_power_w=444.0)
        connection.commit()

    phase = database.latest_phase_sample()
    balance = database.latest_energy_balance_sample()

    assert phase is not None
    assert (phase["ts_epoch"], phase["l1_power_w"]) == (500.0, 111.0)
    assert balance is not None
    assert (balance["ts_epoch"], balance["house_power_w"]) == (500.0, 333.0)


def test_latest_lookups_do_not_scan_detail_tables(tmp_path: Path) -> None:
    """Every lookup starts at the timestamp index instead of a full scan."""

    database = Database(tmp_path / "plans.db")
    with database.connect() as connection:
        sample_id = _insert_sample(connection, 700.0)
        _insert_grid_meter_row(connection, sample_id)
        _insert_phase_row(connection, sample_id)
        _insert_balance_row(connection, sample_id)
        connection.commit()

        plans = {
            "grid": (
                LATEST_GRID_METER_SQL,
                (LATEST_SAMPLE_WINDOW, "grid_meter_primary"),
            ),
            "phase": (LATEST_PHASE_SQL, (LATEST_SAMPLE_WINDOW, "house_meter")),
            "balance": (LATEST_ENERGY_BALANCE_SQL, (LATEST_SAMPLE_WINDOW,)),
        }
        details = {
            name: _plan(connection, sql, parameters)
            for name, (sql, parameters) in plans.items()
        }

    for name, detail in details.items():
        assert "idx_samples_ts_epoch" in detail, (name, detail)
        # Walking the newest samples through the timestamp index is intended;
        # a plain table scan or a scan of a detail table is not.
        assert "SCAN samples " not in detail.replace(
            "SCAN samples USING INDEX idx_samples_ts_epoch", ""
        ), (name, detail)
        for table in (
            "grid_meter_samples",
            "phase_samples",
            "energy_balance_samples",
        ):
            assert f"SCAN {table}" not in detail, (name, detail)


def test_asset_version_tracks_content(tmp_path: Path) -> None:
    """The cache-busting token changes only when an asset changes."""

    static = tmp_path / "static"
    static.mkdir()
    (static / "app.css").write_text("body { color: black; }", encoding="utf-8")
    (static / "dashboard.js").write_text("const a = 1;", encoding="utf-8")

    first = compute_asset_version(static)
    unchanged = compute_asset_version(static)
    (static / "dashboard.js").write_text("const a = 2;", encoding="utf-8")
    changed = compute_asset_version(static)

    assert first == unchanged
    assert changed != first
    assert len(first) == 12
