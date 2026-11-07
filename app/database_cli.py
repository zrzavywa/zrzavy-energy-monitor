#!/usr/bin/env python3
"""Run Zrzavy Energy Monitor database maintenance without application side effects."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Sequence

from zrzavy_energy_monitor_core.paths import DB_PATH
from zrzavy_energy_monitor_core.persistence.maintenance import (
    DatabaseInspection,
    DatabaseMaintenanceError,
    apply_retention,
    create_database_backup,
    dry_run_database_migration,
    inspect_database,
    migrate_database_with_backup,
    plan_retention,
)
from zrzavy_energy_monitor_core.persistence.migrations import DatabaseSchemaError
from zrzavy_energy_monitor_core.services.version import read_installed_version

EXIT_SUCCESS = 0
EXIT_OPERATION_FAILED = 3
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse side-effect-free database maintenance arguments.

    Args:
        argv: Optional argument sequence. ``None`` uses process arguments.

    Returns:
        Validated argparse namespace.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Zrzavy Energy Monitor SQLite prüfen, sichern oder kontrolliert migrieren; "
            "startet weder Webserver noch Collector oder Gerätezugriffe."
        )
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--check-database",
        action="store_true",
        help="Integrität, Lesbarkeit und Migrationsplan prüfen",
    )
    action.add_argument(
        "--database-info",
        action="store_true",
        help="Schema-Version, Plan und sichere Tabellenzähler anzeigen",
    )
    action.add_argument(
        "--backup-database",
        action="store_true",
        help="Konsistentes geprüftes SQLite-Backup erstellen",
    )
    action.add_argument(
        "--migrate-database",
        action="store_true",
        help="Nach Pflicht-Backup auf das Zielschema migrieren",
    )
    action.add_argument(
        "--retention-dry-run",
        action="store_true",
        help="Nur zählen, wie viele Rohdatenzeilen eine Aufbewahrungsfrist löschen würde",
    )
    action.add_argument(
        "--apply-retention",
        action="store_true",
        help="Rohdaten älter als die Aufbewahrungsfrist in einer Transaktion löschen",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Migration nur auf temporärer Kopie ausführen und prüfen",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DB_PATH,
        help=f"Datenbankpfad (Standard: {DB_PATH})",
    )
    parser.add_argument(
        "--backup-directory",
        type=Path,
        help="Backup-Verzeichnis (Standard: <Datenbankordner>/backups)",
    )
    parser.add_argument(
        "--application-version",
        default=read_installed_version(PROJECT_ROOT / "VERSION"),
        help="Anwendungsversion für den Migrationsnachweis",
    )
    parser.add_argument(
        "--keep-raw-days",
        type=int,
        default=730,
        help="Tage Rohdaten, die bei der Aufbewahrung erhalten bleiben (Standard: 730)",
    )
    args = parser.parse_args(argv)
    if args.dry_run and not (args.migrate_database or args.apply_retention):
        parser.error(
            "--dry-run ist nur mit --migrate-database oder --apply-retention zulässig"
        )
    if args.dry_run and args.apply_retention:
        args.retention_dry_run = True
        args.apply_retention = False
    return args


def _run_retention(args: argparse.Namespace) -> int:
    """Plan or apply raw-data retention without touching the schema plan."""
    try:
        plan = plan_retention(args.database, args.keep_raw_days)
        _print_retention_plan(plan)
        if args.retention_dry_run:
            print("Retention-Dry-Run: OK; keine Zeile gelöscht")
            return EXIT_SUCCESS
        result = apply_retention(args.database, plan)
        print(
            "Retention: OK; "
            f"{result.deleted_samples} Samples und "
            f"{sum(result.deleted_dependent_counts.values())} abhängige Zeilen "
            "gelöscht"
        )
        print("Hinweis: Der Dateiplatz wird erst nach einem VACUUM frei.")
        return EXIT_SUCCESS
    except (
        DatabaseMaintenanceError,
        DatabaseSchemaError,
        sqlite3.DatabaseError,
        OSError,
        ValueError,
    ) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return EXIT_OPERATION_FAILED


def _print_retention_plan(plan) -> None:
    """Print how many rows a retention rule would delete."""
    print(
        f"Aufbewahrung: {plan.keep_raw_days} Tage Rohdaten; "
        f"Grenze ts_epoch={plan.cutoff_epoch:.0f}"
    )
    print(f"Samples älter als die Grenze: {plan.sample_count}")
    for name, count in sorted(plan.dependent_counts.items()):
        print(f"  {name}: {count}")
    print(f"Zeilen gesamt: {plan.total_row_count}")


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one database-only maintenance command.

    Args:
        argv: Optional argument sequence for tests or embedding.

    Returns:
        ``0`` on success, ``3`` for database, schema, path, or operating-system
        failures. Invalid CLI syntax uses argparse exit code ``2``.

    Side Effects:
        Check/info are read-only. Backup creates one private file. Dry-run
        creates only a temporary copy. Migration creates and verifies a backup
        before modifying the source transactionally.
    """

    args = parse_args(argv)
    backup_directory = args.backup_directory or args.database.parent / "backups"
    if args.retention_dry_run or args.apply_retention:
        return _run_retention(args)
    try:
        inspection = inspect_database(args.database)
        _print_plan(inspection)
        if args.check_database:
            print("Datenbankprüfung: OK")
        elif args.database_info:
            _print_info(inspection)
        elif args.backup_database:
            backup = create_database_backup(
                args.database,
                backup_directory,
                target_schema_version=inspection.target_schema_version,
            )
            print(f"Backup: {backup.backup_path}")
            print(f"Backup-Integrität: {backup.integrity_check}")
        elif args.dry_run:
            result = dry_run_database_migration(
                args.database,
                application_version=args.application_version,
            )
            print(
                "Dry Run: OK; Quelldatenbank unverändert; "
                f"Zielschema={result.target_schema_version}"
            )
        else:
            result = migrate_database_with_backup(
                args.database,
                backup_directory,
                application_version=args.application_version,
                backup_created=lambda path: print(f"Verifiziertes Backup: {path}"),
            )
            print(
                "Migration: OK; "
                f"Schema {result.previous_schema_version} -> "
                f"{result.target_schema_version}; "
                f"Integrität={result.integrity_check}"
            )
    except (
        DatabaseMaintenanceError,
        DatabaseSchemaError,
        sqlite3.DatabaseError,
        OSError,
        ValueError,
    ) as exc:
        print(f"Datenbankoperation fehlgeschlagen: {exc}", file=sys.stderr)
        return EXIT_OPERATION_FAILED
    return EXIT_SUCCESS


def _print_plan(inspection: DatabaseInspection) -> None:
    versions = [str(migration.version) for migration in inspection.pending_migrations]
    plan = ", ".join(versions) if versions else "keine"
    print(
        f"Schema: {inspection.current_schema_version}; "
        f"Ziel: {inspection.target_schema_version}; "
        f"Migrationen: {plan}"
    )


def _print_info(inspection: DatabaseInspection) -> None:
    print(f"Integrität: {inspection.integrity_check}")
    print(f"Datenbank: {inspection.database_path}")
    for table, count in sorted(inspection.table_counts.items()):
        print(f"Tabelle {table}: {count}")


if __name__ == "__main__":
    raise SystemExit(main())
