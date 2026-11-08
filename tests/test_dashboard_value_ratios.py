"""Contracts for the per-row self-consumption and autarky percentages.

The table shows one quota pair per period row. These tests pin the formulas, the
undefined cases, the rounding, and the rule that the footer holds the quotient
of the sums instead of the sum of the quotas.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import zrzavy_energy_monitor as si
from zrzavy_energy_monitor_core.services.dashboard import _ratio

QUOTA_SERIES = ("self_consumption_pct", "autarky_pct")


def energy_row(
    timestamp: datetime,
    *,
    solar_wh: float,
    house_wh: float,
    self_consumption_wh: float,
) -> dict[str, Any]:
    """Create one sample row with explicit energy values."""

    return {
        "ts_epoch": timestamp.timestamp(),
        "ts_local": timestamp.isoformat(),
        "solar_wh": solar_wh,
        "house_wh": house_wh,
        "grid_import_wh": max(0.0, house_wh - self_consumption_wh),
        "feed_in_wh": max(0.0, solar_wh - self_consumption_wh),
        "self_consumption_wh": self_consumption_wh,
    }


def local_noon(day: date) -> datetime:
    """Return a timestamp inside the local day bucket of the given date."""

    return datetime(day.year, day.month, day.day, 12, 0).astimezone()


def seed(database: si.Database, rows: list[dict[str, Any]]) -> None:
    """Persist sample rows in insertion order."""

    for row in rows:
        database.insert_sample(row)


def test_row_quotients_match_the_confirmed_reference_numbers(tmp_path: Path) -> None:
    """One row reproduces the 88.3 % and 23.9 % of the verified screenshot."""

    database = si.Database(tmp_path / "reference.db")
    anchor = date(2026, 11, 7)
    base = local_noon(anchor)
    seed(
        database,
        [
            energy_row(
                base,
                solar_wh=8000.0,
                house_wh=32480.0,
                self_consumption_wh=7772.0,
            ),
            energy_row(
                base + timedelta(minutes=20),
                solar_wh=9000.0,
                house_wh=32480.0,
                self_consumption_wh=7773.0,
            ),
            energy_row(
                base + timedelta(minutes=40),
                solar_wh=9400.0,
                house_wh=32480.0,
                self_consumption_wh=7773.0,
            ),
        ],
    )

    dashboard = si.build_dashboard(database, "day", anchor)
    hour = base.hour

    assert dashboard["kpi"]["solar_kwh"] == pytest.approx(26.4)
    assert dashboard["kpi"]["house_kwh"] == pytest.approx(97.44)
    assert dashboard["kpi"]["self_consumption_kwh"] == pytest.approx(23.318)
    assert dashboard["series"]["self_consumption_pct"][hour] == pytest.approx(88.3)
    assert dashboard["series"]["autarky_pct"][hour] == pytest.approx(23.9)
    # The row and the footer carry the same number by construction.
    assert (
        dashboard["series"]["self_consumption_pct"][hour]
        == (dashboard["kpi"]["self_consumption_pct"])
    )
    assert dashboard["series"]["autarky_pct"][hour] == dashboard["kpi"]["autarky_pct"]


def test_zero_generation_leaves_the_ratio_undefined(tmp_path: Path) -> None:
    """A bucket without generation has no self-consumption quota."""

    database = si.Database(tmp_path / "no-solar.db")
    anchor = date(2026, 11, 7)
    base = local_noon(anchor)
    seed(
        database,
        [
            energy_row(
                base,
                solar_wh=0.0,
                house_wh=5000.0,
                self_consumption_wh=0.0,
            )
        ],
    )

    dashboard = si.build_dashboard(database, "day", anchor)

    assert dashboard["series"]["self_consumption_pct"][base.hour] is None
    # A measured zero self-consumption is a real result, not an undefined one.
    assert dashboard["series"]["autarky_pct"][base.hour] == pytest.approx(0.0)


def test_zero_house_demand_leaves_autarky_undefined(tmp_path: Path) -> None:
    """A bucket without house demand has no autarky degree."""

    database = si.Database(tmp_path / "no-house.db")
    anchor = date(2026, 11, 7)
    base = local_noon(anchor)
    seed(
        database,
        [energy_row(base, solar_wh=5000.0, house_wh=0.0, self_consumption_wh=0.0)],
    )

    dashboard = si.build_dashboard(database, "day", anchor)

    assert dashboard["series"]["autarky_pct"][base.hour] is None
    assert dashboard["series"]["self_consumption_pct"][base.hour] == pytest.approx(0.0)


def test_rows_without_samples_are_marked_by_the_sample_count(tmp_path: Path) -> None:
    """Future days stay distinguishable from measured zero days."""

    database = si.Database(tmp_path / "partial-month.db")
    anchor = date(2026, 11, 7)
    seed(
        database,
        [
            energy_row(
                local_noon(date(2026, 11, 1)),
                solar_wh=1000.0,
                house_wh=2000.0,
                self_consumption_wh=500.0,
            )
        ],
    )

    dashboard = si.build_dashboard(database, "month", anchor)
    counts = dashboard["series"]["sample_count"]

    assert len(counts) == 30
    assert counts[0] == 1
    assert counts[1:] == [0] * 29
    assert dashboard["series"]["self_consumption_pct"][0] == pytest.approx(50.0)
    assert dashboard["series"]["self_consumption_pct"][20] is None
    assert dashboard["series"]["autarky_pct"][20] is None


def test_ratio_rounds_half_to_even_like_the_existing_kpi() -> None:
    """The helper reuses the rounding of the existing period KPIs."""

    assert _ratio([1.0], [3.0]) == [pytest.approx(33.3)]
    # Python rounds .5 to the even digit; a change here would alter the KPI too.
    assert _ratio([88.25], [100.0]) == [88.2]
    assert _ratio([0.0], [0.0]) == [None]


def test_footer_holds_the_quotient_of_the_sums(tmp_path: Path) -> None:
    """The period KPI is not the mean of the row percentages."""

    database = si.Database(tmp_path / "footer.db")
    anchor = date(2026, 11, 2)  # A Monday, so the week starts on the anchor.
    seed(
        database,
        [
            energy_row(
                local_noon(date(2026, 11, 2)),
                solar_wh=1000.0,
                house_wh=1000.0,
                self_consumption_wh=1000.0,
            ),
            energy_row(
                local_noon(date(2026, 11, 3)),
                solar_wh=100000.0,
                house_wh=100000.0,
                self_consumption_wh=1000.0,
            ),
        ],
    )

    dashboard = si.build_dashboard(database, "week", anchor)
    rows = dashboard["series"]["self_consumption_pct"]

    assert rows[0] == pytest.approx(100.0)
    assert rows[1] == pytest.approx(1.0)
    assert dashboard["kpi"]["self_consumption_pct"] == pytest.approx(2.0)
    mean_of_rows = (rows[0] + rows[1]) / 2
    assert dashboard["kpi"]["self_consumption_pct"] != pytest.approx(mean_of_rows)


@pytest.mark.parametrize("period", ["day", "week", "month", "year"])
def test_quota_series_have_one_value_per_label(tmp_path: Path, period: str) -> None:
    """Every quota series follows the label count of its period."""

    database = si.Database(tmp_path / f"lengths-{period}.db")
    anchor = date(2026, 11, 7)
    seed(
        database,
        [
            energy_row(
                local_noon(anchor),
                solar_wh=1000.0,
                house_wh=2000.0,
                self_consumption_wh=500.0,
            )
        ],
    )

    dashboard = si.build_dashboard(database, period, anchor)

    for key in QUOTA_SERIES + ("sample_count",):
        assert len(dashboard["series"][key]) == len(dashboard["labels"])
    assert sum(dashboard["series"]["sample_count"]) == dashboard["kpi"]["sample_count"]
