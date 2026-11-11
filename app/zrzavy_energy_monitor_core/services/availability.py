"""Aggregate persisted availability counters into display buckets.

The collector stores one counter row per device and UTC hour. This module
turns those rows into hourly buckets, axis ticks and summaries for the
acquisition page. It only reads; it never writes measurement data.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

AVAILABILITY_PERIODS: Final = ("day", "week", "month")
BUCKET_SECONDS: Final = 3600
WEEKDAYS_SHORT: Final = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
MONTH_NAMES: Final = (
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
)
WEEKDAY_NAMES: Final = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)


@dataclass(frozen=True, slots=True)
class AvailabilityWindow:
    """Describe one display period in local wall-clock time."""

    period: str
    start: datetime
    end: datetime
    title: str
    bucket_count: int
    tick_indices: tuple[int, ...]
    tick_labels: tuple[str, ...]


def resolve_local_timezone() -> Any:
    """Return the local IANA timezone, else the fixed local offset.

    A bare UTC offset cannot represent daylight saving time, so a named zone
    is resolved from TZ or the system link. Without either, the fixed offset
    is used and daylight saving days stay 24 hours wide.
    """

    candidate = os.environ.get("TZ", "").strip()
    if candidate:
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    try:
        target = os.readlink(Path("/etc/localtime"))
    except OSError:
        target = ""
    marker = "zoneinfo/"
    if marker in target:
        try:
            return ZoneInfo(target.split(marker, 1)[1])
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return datetime.now().astimezone().tzinfo


def availability_window(period: str, anchor: date, tz: Any) -> AvailabilityWindow:
    """Return the local period window with its axis ticks.

    Boundaries are built from local calendar dates, so a daylight saving day
    yields 23 or 25 hourly buckets instead of a fixed 24.
    """

    normalized = period if period in AVAILABILITY_PERIODS else "day"
    if normalized == "week":
        first_day = anchor - timedelta(days=anchor.weekday())
        last_day = first_day + timedelta(days=7)
        title = (
            f"Woche {first_day.isocalendar().week} · {first_day:%d.%m.}"
            f"–{last_day - timedelta(days=1):%d.%m.%Y}"
        )
    elif normalized == "month":
        first_day = date(anchor.year, anchor.month, 1)
        last_day = (
            date(anchor.year + 1, 1, 1)
            if anchor.month == 12
            else date(anchor.year, anchor.month + 1, 1)
        )
        title = f"{MONTH_NAMES[anchor.month - 1]} {anchor.year}"
    else:
        first_day = anchor
        last_day = anchor + timedelta(days=1)
        title = f"{WEEKDAY_NAMES[anchor.weekday()]}, {anchor:%d.%m.%Y}"

    start = datetime(first_day.year, first_day.month, first_day.day, tzinfo=tz)
    end = datetime(last_day.year, last_day.month, last_day.day, tzinfo=tz)
    # Aware datetimes in the same zone subtract as wall-clock time, which hides
    # the daylight saving shift. Compare absolute instants instead.
    bucket_count = max(
        0,
        int((end.timestamp() - start.timestamp()) // BUCKET_SECONDS),
    )
    tick_indices, tick_labels = _axis_ticks(
        normalized,
        first_day,
        last_day,
        start,
        tz,
        bucket_count,
    )
    return AvailabilityWindow(
        period=normalized,
        start=start,
        end=end,
        title=title,
        bucket_count=bucket_count,
        tick_indices=tick_indices,
        tick_labels=tick_labels,
    )


def _axis_ticks(
    period: str,
    first_day: date,
    last_day: date,
    start: datetime,
    tz: Any,
    bucket_count: int,
) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """Return bucket indices and labels for the chart axis."""

    indices: list[int] = []
    labels: list[str] = []
    if period == "day":
        for hour in range(0, bucket_count, 3):
            indices.append(hour)
            labels.append(f"{hour:02d}:00")
        return tuple(indices), tuple(labels)

    day = first_day
    while day < last_day:
        midnight = datetime(day.year, day.month, day.day, tzinfo=tz)
        index = int((midnight.timestamp() - start.timestamp()) // BUCKET_SECONDS)
        if period == "week":
            indices.append(index)
            labels.append(f"{WEEKDAYS_SHORT[day.weekday()]} {day:%d.%m.}")
        elif (day.day - 1) % 5 == 0:
            indices.append(index)
            labels.append(f"{day:%d.%m.}")
        day += timedelta(days=1)
    return tuple(indices), tuple(labels)


def build_availability_api_response(
    database: Any,
    devices: Sequence[Mapping[str, Any]],
    period: str,
    anchor_value: str | None,
    *,
    timezone: Any = None,
) -> dict[str, Any]:
    """Build the device-availability payload for one display period.

    Args:
        database: Object offering availability_hours_between.
        devices: Card records with role, source_id, title and transport.
        period: day, week or month. Unknown values fall back to day.
        anchor_value: ISO date of the displayed period, or None for today.
        timezone: Optional timezone; the local zone is used by default.

    Returns:
        Period metadata plus one bucket series and summary per device.
    """

    tz = timezone if timezone is not None else resolve_local_timezone()
    anchor = _parse_anchor(anchor_value, tz)
    window = availability_window(period, anchor, tz)
    start_epoch = window.start.timestamp()
    end_epoch = window.end.timestamp()

    requested = sorted({_text(device.get("source_id")) for device in devices})
    requested = [source for source in requested if source]
    rows_by_source = _rows_by_source(
        database,
        start_epoch=start_epoch,
        end_epoch=end_epoch,
        source_ids=tuple(requested),
    )

    series: list[dict[str, Any]] = []
    for device in devices:
        source_id = _text(device.get("source_id"))
        configured = bool(device.get("enabled")) and bool(device.get("configured"))
        buckets, summary = _bucket_series(
            rows_by_source.get(source_id, []),
            start_epoch=start_epoch,
            bucket_count=window.bucket_count,
            configured=configured,
        )
        series.append(
            {
                "role": _text(device.get("role")),
                "source_id": source_id,
                "name": _text(device.get("title")),
                "adapter": _text(device.get("transport")),
                "configured": configured,
                "coverage": summary["coverage"],
                "state": summary["state"],
                "buckets": buckets,
                "summary": summary,
            }
        )

    return {
        "period": window.period,
        "anchor": anchor.isoformat(),
        "title": window.title,
        "timezone": _timezone_name(tz),
        "bucket_seconds": BUCKET_SECONDS,
        "bucket_count": window.bucket_count,
        "period_start_epoch": start_epoch,
        "period_end_epoch": end_epoch,
        "tick_indices": list(window.tick_indices),
        "tick_labels": list(window.tick_labels),
        "devices": series,
    }


def _rows_by_source(
    database: Any,
    *,
    start_epoch: float,
    end_epoch: float,
    source_ids: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    """Read and group hourly availability rows by source."""

    reader = getattr(database, "availability_hours_between", None)
    if not callable(reader) or not source_ids:
        return {}
    rows = reader(start_epoch, end_epoch, source_ids=source_ids)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_text(row.get("source_id")), []).append(row)
    return grouped


def _bucket_series(
    rows: Sequence[Mapping[str, Any]],
    *,
    start_epoch: float,
    bucket_count: int,
    configured: bool,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Fold hourly rows into bucket counters and one summary."""

    buckets = [[0, 0, 0, 0] for _ in range(bucket_count)]
    origins: set[str] = set()
    unknown_total = 0
    first_seen: float | None = None
    last_seen: float | None = None
    for row in rows:
        hour_start = int(row.get("hour_start") or 0)
        # An hour row belongs to the bucket holding its midpoint, which is
        # exact for the one-hour buckets this API returns.
        index = int((hour_start + BUCKET_SECONDS / 2 - start_epoch) // BUCKET_SECONDS)
        online = int(row.get("online_count") or 0)
        degraded = int(row.get("degraded_count") or 0)
        offline = int(row.get("offline_count") or 0)
        disabled = int(row.get("disabled_count") or 0)
        unknown_total += int(row.get("unknown_count") or 0)
        origins.add(_text(row.get("origin")) or "recorded")
        observed_first = _optional_float(row.get("first_seen_epoch"))
        if observed_first is not None:
            first_seen = (
                observed_first
                if first_seen is None
                else min(first_seen, observed_first)
            )
        observed_last = _optional_float(row.get("last_seen_epoch"))
        if observed_last is not None:
            last_seen = (
                observed_last if last_seen is None else max(last_seen, observed_last)
            )
        if 0 <= index < bucket_count:
            buckets[index][0] += online
            buckets[index][1] += degraded
            buckets[index][2] += offline
            buckets[index][3] += disabled

    totals = [sum(bucket[position] for bucket in buckets) for position in range(4)]
    observed_total = sum(totals)
    hours_observed = sum(1 for bucket in buckets if sum(bucket) > 0)
    if not configured:
        coverage = "none"
    elif "recorded" in origins:
        coverage = "recorded"
    elif origins:
        coverage = "derived"
    else:
        coverage = "none"

    summary: dict[str, Any] = {
        "coverage": coverage,
        "state": _current_state(buckets),
        "observations": observed_total,
        "unknown_observations": unknown_total,
        "hours_observed": hours_observed,
        "hours_in_period": bucket_count,
        "reachable_pct": _percentage(totals[0] + totals[1], observed_total),
        "unreachable_pct": _percentage(totals[2], observed_total),
        "degraded_pct": _percentage(totals[1], observed_total),
        "inactive_pct": _percentage(totals[3], observed_total),
        "first_seen_epoch": first_seen,
        "last_seen_epoch": last_seen,
    }
    return buckets, summary


def _current_state(buckets: Sequence[Sequence[int]]) -> str:
    """Return the display state of the newest observed bucket.

    Reachability decides the state; degraded readings stay reachable and are
    reported separately, so a permanent diagnosis does not turn a working
    device into a permanent outage.
    """

    for bucket in reversed(buckets):
        online, degraded, offline, disabled = bucket
        observed = online + degraded + offline + disabled
        if not observed:
            continue
        if disabled == observed:
            return "inactive"
        if offline >= observed / 2:
            return "bad"
        if offline:
            return "limited"
        return "good"
    return "nodata"


def _percentage(part: int, total: int) -> float | None:
    """Return a rounded percentage or None without observations."""

    if total <= 0:
        return None
    return round(part * 100.0 / total, 1)


def _parse_anchor(value: str | None, tz: Any) -> date:
    """Return the requested local date or today."""

    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(tz).date()


def _timezone_name(tz: Any) -> str:
    """Return a readable timezone identifier."""

    key = getattr(tz, "key", None)
    return str(key) if key else str(tz)


def _optional_float(value: object) -> float | None:
    """Convert an optional numeric value without raising."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str:
    """Return trimmed text for an optional value."""

    return "" if value is None else str(value).strip()
