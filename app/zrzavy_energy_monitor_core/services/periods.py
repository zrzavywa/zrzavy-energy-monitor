"""Calculate existing SolarInspector dashboard periods and buckets.

This module preserves the date parsing, period boundaries, labels, titles,
and bucket assignment behavior of SolarInspector 4.1.3.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional


def parse_anchor(value: Optional[str]) -> date:
    """parse_anchor provides the public operation implemented by this component."""
    if not value:
        return datetime.now().astimezone().date()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return datetime.now().astimezone().date()


def period_bounds(
    period: str, anchor: date
) -> tuple[datetime, datetime, list[str], str]:
    """period_bounds provides the public operation implemented by this component."""
    tz = datetime.now().astimezone().tzinfo
    weekdays_short = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    weekdays_long = [
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag",
        "Freitag",
        "Samstag",
        "Sonntag",
    ]
    month_names = [
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ]
    if period == "week":
        start_date = anchor - timedelta(days=anchor.weekday())
        start = datetime.combine(start_date, datetime.min.time(), tzinfo=tz)
        end = start + timedelta(days=7)
        labels = [
            f"{weekdays_short[i]} {(start_date + timedelta(days=i)):%d.%m.}"
            for i in range(7)
        ]
        title = f"Woche {start_date.isocalendar().week} · {start_date:%d.%m.}–{(start_date + timedelta(days=6)):%d.%m.%Y}"
    elif period == "month":
        month_start = date(anchor.year, anchor.month, 1)
        if anchor.month == 12:
            next_month = date(anchor.year + 1, 1, 1)
        else:
            next_month = date(anchor.year, anchor.month + 1, 1)
        start = datetime.combine(month_start, datetime.min.time(), tzinfo=tz)
        end = datetime.combine(next_month, datetime.min.time(), tzinfo=tz)
        labels = [
            f"{(month_start + timedelta(days=offset)):%d.%m.}"
            for offset in range((next_month - month_start).days)
        ]
        title = f"{month_names[anchor.month - 1]} {anchor.year}"
    elif period == "year":
        start = datetime(anchor.year, 1, 1, tzinfo=tz)
        end = datetime(anchor.year + 1, 1, 1, tzinfo=tz)
        labels = [
            "Jan",
            "Feb",
            "Mär",
            "Apr",
            "Mai",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Okt",
            "Nov",
            "Dez",
        ]
        title = f"Jahr {anchor.year}"
    else:
        period = "day"
        start = datetime.combine(anchor, datetime.min.time(), tzinfo=tz)
        end = start + timedelta(days=1)
        labels = [f"{hour:02d}:00" for hour in range(24)]
        title = f"{weekdays_long[anchor.weekday()]}, {anchor:%d.%m.%Y}"
    return start, end, labels, title


def bucket_index(period: str, start: datetime, sample_dt: datetime) -> int:
    """bucket_index provides the public operation implemented by this component."""
    if period == "week":
        return (sample_dt.date() - start.date()).days
    if period == "month":
        return (sample_dt.date() - start.date()).days
    if period == "year":
        return sample_dt.month - 1
    return sample_dt.hour
