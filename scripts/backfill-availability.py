#!/usr/bin/env python3
"""Derive hourly availability counters from already persisted samples."""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from zrzavy_energy_monitor_core.paths import DB_PATH  # noqa: E402
from zrzavy_energy_monitor_core.persistence.availability_backfill import (  # noqa: E402
    backfill_availability,
)

EXIT_SUCCESS = 0
EXIT_OPERATION_FAILED = 3


def main() -> int:
    """Run one bounded, idempotent availability backfill."""

    parser = argparse.ArgumentParser(
        description=(
            "Erreichbarkeits-Stundenzähler aus vorhandenen Messzeilen ableiten. "
            "Ohne --apply wird nur gezählt."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DB_PATH,
        help=f"Datenbankpfad (Standard: {DB_PATH})",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Anzahl Tage rückwärts ab jetzt (Standard: 30)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Abgeleitete Zeilen tatsächlich schreiben",
    )
    args = parser.parse_args()

    end_epoch = time.time()
    start_epoch = end_epoch - args.days * 86_400
    try:
        result = backfill_availability(
            args.database,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            apply=args.apply,
        )
    except (sqlite3.DatabaseError, OSError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return EXIT_OPERATION_FAILED

    print(
        f"Netzzähler: {result.grid_meter_rows} Stunden; "
        f"Phasenmessung: {result.house_phase_rows} Stunden; "
        f"Binärsignale: {result.flag_rows} Stunden; "
        f"gesamt: {result.total_rows}"
    )
    if args.apply:
        print("Backfill: OK; abgeleitete Zeilen mit origin='derived' gespeichert")
    else:
        print("Backfill-Dry-Run: OK; keine Zeile geschrieben")
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
