"""Tests for the SQL-backed dashboard aggregation and the month period."""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import pytest
import zrzavy_energy_monitor as si
from zrzavy_energy_monitor_core.web.api import build_dashboard_api_response

pytestmark = pytest.mark.characterization

ENERGY_KEYS = (
    "solar_wh",
    "house_wh",
    "grid_import_wh",
    "feed_in_wh",
    "self_consumption_wh",
    "shelly_solar_wh",
    "solakon_pv_wh",
    "solakon_ac_wh",
    "battery_charge_wh",
    "battery_discharge_wh",
)


@pytest.fixture
def berlin_timezone() -> Iterator[None]:
    """Run one test with the productive Europe/Berlin timezone."""

    previous = os.environ.get("TZ")
    os.environ["TZ"] = "Europe/Berlin"
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


def sample_row(
    timestamp: datetime,
    *,
    index: int,
    soc: float | None = None,
    difference_w: float | None = None,
    difference_pct: float | None = None,
    solar_source: str = "Shelly",
    grid_source: str = "Grid",
) -> dict[str, Any]:
    """Create one persisted sample row with deterministic values."""

    base = float(index + 1)
    return {
        "ts_epoch": timestamp.timestamp(),
        "ts_local": timestamp.isoformat(),
        "solar_wh": base * 10.0,
        "house_wh": base * 20.0,
        "grid_import_wh": base * 5.0,
        "feed_in_wh": base * 2.0,
        "self_consumption_wh": base * 8.0,
        "shelly_solar_wh": base * 9.0,
        "solakon_pv_wh": base * 11.0,
        "solakon_ac_wh": base * 7.0,
        "battery_charge_wh": base * 3.0,
        "battery_discharge_wh": base * 1.5,
        "solakon_battery_soc_pct": soc,
        "solar_difference_w": difference_w,
        "solar_difference_pct": difference_pct,
        "solar_source": solar_source,
        "grid_source": grid_source,
    }


def seed(database: si.Database, rows: list[dict[str, Any]]) -> None:
    """Persist sample rows in insertion order."""

    for row in rows:
        database.insert_sample(row)


def reference_dashboard(
    database: si.Database,
    period: str,
    anchor: date,
) -> dict[str, Any]:
    """Rebuild the historical row-wise aggregation as a reference."""

    start, end, labels, title = si.period_bounds(period, anchor)
    rows = database.rows_between(start.timestamp(), end.timestamp())
    buckets = {key: [0.0] * len(labels) for key in ENERGY_KEYS}
    totals = {key: 0.0 for key in ENERGY_KEYS}
    soc_buckets: list[list[float]] = [[] for _ in labels]
    all_soc: list[float] = []
    differences: list[float] = []
    difference_pcts: list[float] = []

    for row in rows:
        sample_dt = datetime.fromtimestamp(float(row["ts_epoch"])).astimezone()
        index = si.bucket_index(period, start, sample_dt)
        if not 0 <= index < len(labels):
            continue
        for key in ENERGY_KEYS:
            value = float(row.get(key) or 0.0)
            buckets[key][index] += value
            totals[key] += value
        soc = row.get("solakon_battery_soc_pct")
        if soc is not None:
            soc_buckets[index].append(float(soc))
            all_soc.append(float(soc))
        if row.get("solar_difference_w") is not None:
            differences.append(float(row["solar_difference_w"]))
        if row.get("solar_difference_pct") is not None:
            difference_pcts.append(float(row["solar_difference_pct"]))

    solar = totals["solar_wh"]
    house = totals["house_wh"]
    self_use = totals["self_consumption_wh"]
    return {
        "labels": labels,
        "title": title,
        "series": {
            key: [round(value / 1000.0, 4) for value in buckets[key]]
            for key in ENERGY_KEYS
        },
        "soc_avg": [
            round(sum(values) / len(values), 1) if values else None
            for values in soc_buckets
        ],
        "kpi": {
            "solar_kwh": round(solar / 1000.0, 3),
            "house_kwh": round(house / 1000.0, 3),
            "grid_import_kwh": round(totals["grid_import_wh"] / 1000.0, 3),
            "feed_in_kwh": round(totals["feed_in_wh"] / 1000.0, 3),
            "self_consumption_kwh": round(self_use / 1000.0, 3),
            "self_consumption_pct": round(self_use / solar * 100.0, 1)
            if solar > 0
            else None,
            "autarky_pct": round(self_use / house * 100.0, 1) if house > 0 else None,
            "battery_soc_avg": round(sum(all_soc) / len(all_soc), 1)
            if all_soc
            else None,
            "battery_soc_min": round(min(all_soc), 1) if all_soc else None,
            "battery_soc_max": round(max(all_soc), 1) if all_soc else None,
            "difference_avg_w": round(sum(differences) / len(differences), 1)
            if differences
            else None,
            "difference_avg_pct": round(sum(difference_pcts) / len(difference_pcts), 1)
            if difference_pcts
            else None,
            "sample_count": len(rows),
        },
    }


def assert_values_close(actual: list[Any], expected: list[Any]) -> None:
    """Compare two value lists that may contain None entries."""

    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        if want is None:
            assert got is None
        else:
            assert got == pytest.approx(want, rel=1e-6, abs=1e-6)


def assert_matches_reference(
    dashboard: dict[str, Any],
    reference: dict[str, Any],
) -> None:
    """Compare a dashboard payload with the row-wise reference result."""

    assert dashboard["labels"] == reference["labels"]
    assert dashboard["title"] == reference["title"]
    reference_series = reference["series"]
    assert_values_close(dashboard["series"]["solar_kwh"], reference_series["solar_wh"])
    assert_values_close(dashboard["series"]["house_kwh"], reference_series["house_wh"])
    assert_values_close(
        dashboard["series"]["grid_import_kwh"], reference_series["grid_import_wh"]
    )
    assert_values_close(
        dashboard["series"]["battery_discharge_kwh"],
        reference_series["battery_discharge_wh"],
    )
    assert_values_close(dashboard["series"]["battery_soc_avg"], reference["soc_avg"])
    for key, expected in reference["kpi"].items():
        if expected is None:
            assert dashboard["kpi"][key] is None
        else:
            assert dashboard["kpi"][key] == pytest.approx(expected, rel=1e-6, abs=1e-6)


def build_rows(start: datetime, count: int, step: timedelta) -> list[dict[str, Any]]:
    """Create evenly spaced sample rows."""

    return [
        sample_row(
            start + step * offset,
            index=offset,
            soc=20.0 + offset % 7,
            difference_w=float(offset % 5) - 2.0,
            difference_pct=float(offset % 3) - 1.0,
            solar_source=f"Shelly {offset % 2}",
            grid_source=f"Grid {offset % 2}",
        )
        for offset in range(count)
    ]


def test_month_bounds_and_labels() -> None:
    """A month period covers its calendar month and labels every day."""

    start, end, labels, title = si.period_bounds("month", date(2026, 11, 7))

    assert start.date() == date(2026, 11, 1)
    assert end.date() == date(2026, 12, 1)
    assert title == "November 2026"
    assert labels[0] == "01.11."
    assert labels[-1] == "30.11."
    assert len(labels) == 30


def test_month_bounds_roll_over_into_next_year() -> None:
    """December ends at the first day of the following year."""

    start, end, labels, _title = si.period_bounds("month", date(2026, 12, 31))

    assert start.date() == date(2026, 12, 1)
    assert end.date() == date(2027, 1, 1)
    assert len(labels) == 31


def test_month_bounds_follow_leap_year() -> None:
    """February uses the calendar length of the requested year."""

    _start, _end, labels, _title = si.period_bounds("month", date(2028, 2, 10))

    assert len(labels) == 29


def test_month_bucket_index_counts_days() -> None:
    """Month buckets count days from the first of the month."""

    start, _end, _labels, _title = si.period_bounds("month", date(2026, 11, 7))

    assert si.bucket_index("month", start, start + timedelta(days=0)) == 0
    assert si.bucket_index("month", start, start + timedelta(days=19)) == 19


@pytest.mark.parametrize("period", ["day", "week", "month", "year"])
def test_dashboard_matches_reference_aggregation(
    tmp_path: Path,
    period: str,
) -> None:
    """SQL aggregation preserves series, KPIs, and counts of the reference."""

    database = si.Database(tmp_path / f"parity-{period}.db")
    anchor = date(2026, 11, 7)
    seed(
        database,
        build_rows(
            datetime(2026, 10, 20, 0, 0).astimezone(),
            60,
            timedelta(hours=13),
        ),
    )

    dashboard = si.build_dashboard(database, period, anchor)
    reference = reference_dashboard(database, period, anchor)

    assert_matches_reference(dashboard, reference)
    assert dashboard["period"] == period


def test_month_aggregation_uses_local_days(
    tmp_path: Path,
    berlin_timezone: None,
) -> None:
    """Daily month buckets follow local calendar days across a DST change."""

    database = si.Database(tmp_path / "dst.db")
    anchor = date(2026, 10, 25)
    local_start = datetime(
        2026, 10, 24, 0, 0, tzinfo=datetime.now().astimezone().tzinfo
    )
    rows = build_rows(local_start, 72, timedelta(hours=1))
    seed(database, rows)

    dashboard = si.build_dashboard(database, "month", anchor)
    reference = reference_dashboard(database, "month", anchor)

    assert_matches_reference(dashboard, reference)
    day_index = 24
    assert dashboard["series"]["solar_kwh"][day_index] == pytest.approx(
        reference["series"]["solar_wh"][day_index], rel=1e-6, abs=1e-6
    )
    assert dashboard["kpi"]["sample_count"] == 72
    assert dashboard["series"]["solar_kwh"][day_index] > 0.0


def test_empty_period_returns_zeroed_series(tmp_path: Path) -> None:
    """An empty period yields zero series and untouched KPI defaults."""

    database = si.Database(tmp_path / "empty.db")
    seed(database, build_rows(datetime(2025, 1, 1).astimezone(), 5, timedelta(hours=1)))

    dashboard = si.build_dashboard(database, "month", date(2026, 11, 7))

    assert dashboard["series"]["solar_kwh"] == [0.0] * 30
    assert dashboard["series"]["battery_soc_avg"] == [None] * 30
    assert dashboard["kpi"]["sample_count"] == 0
    assert dashboard["kpi"]["self_consumption_pct"] is None
    assert dashboard["kpi"]["solar_source"] is None


def test_dashboard_api_accepts_month_and_rejects_unknown(tmp_path: Path) -> None:
    """The HTTP payload builder exposes the month period."""

    database = si.Database(tmp_path / "api.db")
    seed(
        database, build_rows(datetime(2026, 11, 1).astimezone(), 8, timedelta(hours=6))
    )

    month_payload = build_dashboard_api_response(database, "month", "2026-11-07")
    unknown_payload = build_dashboard_api_response(database, "quarter", "2026-11-07")

    assert month_payload["period"] == "month"
    assert month_payload["title"] == "November 2026"
    assert len(month_payload["labels"]) == 30
    assert unknown_payload["period"] == "day"
