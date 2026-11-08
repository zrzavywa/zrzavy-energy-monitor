"""Build the Zrzavy Energy Monitor dashboard data.

Aggregation happens inside SQLite: only per-hour aggregates are transferred
and folded into the requested period buckets. This keeps the weekly, monthly,
and yearly views independent of the number of stored samples while preserving
the historical KPI and series semantics.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from zrzavy_energy_monitor_core.persistence.database import Database
from zrzavy_energy_monitor_core.services.periods import (
    bucket_index,
    period_bounds,
)

ENERGY_SERIES_KEYS = (
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


def _ratio(values: list[float], denominators: list[float]) -> list[float | None]:
    """Return percentages with one decimal, or None where the denominator is 0.

    A missing denominator means the quotient is undefined; the dashboard shows a
    dash there instead of inventing 0 % or 100 %.
    """

    return [
        round(value / denominator * 100.0, 1) if denominator > 0 else None
        for value, denominator in zip(values, denominators)
    ]


def build_dashboard(database: Database, period: str, anchor: date) -> dict[str, Any]:
    """Build one dashboard period from hourly database aggregates."""

    start, end, labels, title = period_bounds(period, anchor)
    bucket_count = len(labels)
    buckets = {key: [0.0] * bucket_count for key in ENERGY_SERIES_KEYS}
    soc_sum = [0.0] * bucket_count
    soc_count = [0] * bucket_count
    soc_min: list[float | None] = [None] * bucket_count
    soc_max: list[float | None] = [None] * bucket_count
    difference_sum = [0.0] * bucket_count
    difference_count = [0] * bucket_count
    difference_pct_sum = [0.0] * bucket_count
    difference_pct_count = [0] * bucket_count
    bucket_sample_count = [0] * bucket_count

    for hour in database.aggregate_samples_by_hour(start.timestamp(), end.timestamp()):
        index = bucket_index(
            period,
            start,
            datetime.fromtimestamp(float(hour["hour_start"]) * 3600).astimezone(),
        )
        if not 0 <= index < bucket_count:
            continue
        bucket_sample_count[index] += int(hour["sample_count"] or 0)
        for key in ENERGY_SERIES_KEYS:
            buckets[key][index] += float(hour[key] or 0.0)
        hour_soc_count = int(hour["soc_count"] or 0)
        if hour_soc_count:
            soc_sum[index] += float(hour["soc_sum"] or 0.0)
            soc_count[index] += hour_soc_count
            low = hour["soc_min"]
            if low is not None:
                low_value = float(low)
                current_low = soc_min[index]
                soc_min[index] = (
                    low_value if current_low is None else min(current_low, low_value)
                )
            high = hour["soc_max"]
            if high is not None:
                high_value = float(high)
                current_high = soc_max[index]
                soc_max[index] = (
                    high_value
                    if current_high is None
                    else max(current_high, high_value)
                )
        hour_difference_count = int(hour["difference_count"] or 0)
        if hour_difference_count:
            difference_sum[index] += float(hour["difference_sum"] or 0.0)
            difference_count[index] += hour_difference_count
        hour_pct_count = int(hour["difference_pct_count"] or 0)
        if hour_pct_count:
            difference_pct_sum[index] += float(hour["difference_pct_sum"] or 0.0)
            difference_pct_count[index] += hour_pct_count

    totals = {key: sum(values) for key, values in buckets.items()}
    sample_count = sum(bucket_sample_count)
    total_soc_count = sum(soc_count)
    total_difference_count = sum(difference_count)
    total_pct_count = sum(difference_pct_count)
    soc_lows = [value for value in soc_min if value is not None]
    soc_highs = [value for value in soc_max if value is not None]
    latest = database.latest_sample_sources(start.timestamp(), end.timestamp())

    solar = totals["solar_wh"]
    house = totals["house_wh"]
    self_use = totals["self_consumption_wh"]

    return {
        "period": period,
        "anchor": anchor.isoformat(),
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "labels": labels,
        "series": {
            "solar_kwh": [round(v / 1000.0, 4) for v in buckets["solar_wh"]],
            "house_kwh": [round(v / 1000.0, 4) for v in buckets["house_wh"]],
            "grid_import_kwh": [
                round(v / 1000.0, 4) for v in buckets["grid_import_wh"]
            ],
            "feed_in_kwh": [round(v / 1000.0, 4) for v in buckets["feed_in_wh"]],
            "self_consumption_kwh": [
                round(v / 1000.0, 4) for v in buckets["self_consumption_wh"]
            ],
            "solakon_pv_kwh": [round(v / 1000.0, 4) for v in buckets["solakon_pv_wh"]],
            "solakon_ac_kwh": [round(v / 1000.0, 4) for v in buckets["solakon_ac_wh"]],
            "battery_charge_kwh": [
                round(v / 1000.0, 4) for v in buckets["battery_charge_wh"]
            ],
            "battery_discharge_kwh": [
                round(v / 1000.0, 4) for v in buckets["battery_discharge_wh"]
            ],
            "battery_soc_avg": [
                round(soc_sum[index] / soc_count[index], 1)
                if soc_count[index]
                else None
                for index in range(bucket_count)
            ],
            # Per-bucket percentages use the same formulas and denominator rules
            # as the period KPIs, so a row and the footer never disagree.
            "self_consumption_pct": _ratio(
                buckets["self_consumption_wh"], buckets["solar_wh"]
            ),
            "autarky_pct": _ratio(buckets["self_consumption_wh"], buckets["house_wh"]),
            # Rows without a single sample stay distinguishable from measured
            # zeros; the table renders those quota cells as a dash.
            "sample_count": bucket_sample_count,
        },
        "kpi": {
            "solar_kwh": round(solar / 1000.0, 3),
            "house_kwh": round(house / 1000.0, 3),
            "grid_import_kwh": round(totals["grid_import_wh"] / 1000.0, 3),
            "feed_in_kwh": round(totals["feed_in_wh"] / 1000.0, 3),
            "self_consumption_kwh": round(self_use / 1000.0, 3),
            "self_consumption_pct": round((self_use / solar * 100.0), 1)
            if solar > 0
            else None,
            "autarky_pct": round((self_use / house * 100.0), 1) if house > 0 else None,
            "sample_count": sample_count,
            "shelly_ac_kwh": round(totals["shelly_solar_wh"] / 1000.0, 3),
            "solakon_pv_kwh": round(totals["solakon_pv_wh"] / 1000.0, 3),
            "solakon_ac_kwh": round(totals["solakon_ac_wh"] / 1000.0, 3),
            "battery_charge_kwh": round(totals["battery_charge_wh"] / 1000.0, 3),
            "battery_discharge_kwh": round(totals["battery_discharge_wh"] / 1000.0, 3),
            "battery_soc_avg": round(sum(soc_sum) / total_soc_count, 1)
            if total_soc_count
            else None,
            "battery_soc_min": round(min(soc_lows), 1) if soc_lows else None,
            "battery_soc_max": round(max(soc_highs), 1) if soc_highs else None,
            "difference_avg_w": round(sum(difference_sum) / total_difference_count, 1)
            if total_difference_count
            else None,
            "difference_avg_pct": round(sum(difference_pct_sum) / total_pct_count, 1)
            if total_pct_count
            else None,
            "solar_source": latest.get("solar_source") if latest else None,
            "grid_source": latest.get("grid_source") if latest else None,
        },
    }
