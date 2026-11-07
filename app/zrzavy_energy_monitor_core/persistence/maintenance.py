"""Safe file-level backup, inspection, and migration orchestration."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Final, Iterator

from zrzavy_energy_monitor_core.persistence.migrations import (
    Migration,
    apply_migrations,
    get_current_version,
    get_target_version,
    plan_migrations,
    verify_schema,
)

PRIVATE_DIRECTORY_MODE: Final = 0o700
PRIVATE_FILE_MODE: Final = 0o600
_COUNTED_TABLES: Final = (
    "samples",
    "phase_samples",
    "grid_meter_samples",
    "validation_events",
    "energy_balance_samples",
    "measurements",
    "source_selection_events",
)


class DatabaseMaintenanceError(RuntimeError):
    """Report a safe database maintenance precondition or verification error."""


@dataclass(frozen=True)
class DatabaseInspection:
    """Describe read-only database integrity, schema, and optional row counts."""

    database_path: Path
    integrity_check: str
    current_schema_version: int
    target_schema_version: int
    pending_migrations: tuple[Migration, ...]
    table_counts: dict[str, int]


@dataclass(frozen=True)
class DatabaseBackup:
    """Describe one verified, private SQLite backup file."""

    source_path: Path
    backup_path: Path
    source_schema_version: int
    target_schema_version: int
    integrity_check: str
    sample_count: int | None


@dataclass(frozen=True)
class MigrationRun:
    """Describe a dry-run or committed migration outcome."""

    database_path: Path
    dry_run: bool
    previous_schema_version: int
    target_schema_version: int
    applied_migrations: tuple[Migration, ...]
    integrity_check: str
    backup_path: Path | None


def inspect_database(
    database_path: Path,
    *,
    verify_integrity: bool = True,
    count_rows: bool = True,
) -> DatabaseInspection:
    """Inspect a SQLite database without creating or modifying it.

    Args:
        database_path: Existing regular database file.
        verify_integrity: Run SQLite's full PRAGMA integrity_check.
        count_rows: Count rows in known readable tables.

    Returns:
        Schema versions and pending plan, with optional integrity and table
        counts. A skipped integrity check is reported as not_checked; a skipped
        row-count pass returns an empty mapping. No row contents or secrets are
        returned.

    Raises:
        DatabaseMaintenanceError: If the path is missing, not a regular file,
            unreadable, or a requested integrity check fails.
        DatabaseSchemaError: If version metadata is incompatible.

    Side Effects:
        Opens the database in SQLite read-only/query-only mode. It does not
        create WAL files, start application services, or access devices.
    """

    path = _existing_database_path(database_path)
    try:
        with _read_only_connection(path) as connection:
            integrity = "not_checked"
            if verify_integrity:
                integrity = _integrity_result(connection)
                if integrity != "ok":
                    raise DatabaseMaintenanceError(
                        f"database integrity check failed: {integrity}"
                    )
            current_version = get_current_version(connection)
            counts = {}
            if count_rows:
                counts = {
                    table: int(
                        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[
                            0
                        ]
                    )
                    for table in _COUNTED_TABLES
                    if _table_exists(connection, table)
                }
    except sqlite3.DatabaseError as exc:
        raise DatabaseMaintenanceError(f"database cannot be inspected: {path}") from exc
    return DatabaseInspection(
        database_path=path,
        integrity_check=integrity,
        current_schema_version=current_version,
        target_schema_version=get_target_version(),
        pending_migrations=plan_migrations(current_version),
        table_counts=counts,
    )


def create_database_backup(
    database_path: Path,
    backup_directory: Path,
    *,
    target_schema_version: int,
    created_at: datetime | None = None,
) -> DatabaseBackup:
    """Create and verify one consistent private SQLite backup.

    Args:
        database_path: Existing source database. It remains unchanged.
        backup_directory: Directory created with mode ``0700`` when absent.
        target_schema_version: Planned target included in the filename.
        created_at: Optional timezone-aware timestamp; defaults to UTC now.

    Returns:
        Metadata for the verified ``0600`` backup.

    Raises:
        ValueError: If the target version or timestamp is invalid.
        DatabaseMaintenanceError: If paths are unsafe, integrity fails, the
            destination exists, or source/backup verification differs.
        OSError: If private directory or file operations fail.

    Side Effects:
        Uses SQLite's online backup API, atomically publishes one new file,
        and never overwrites an existing backup.
    """

    if target_schema_version < 1:
        raise ValueError("target_schema_version must be positive")
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.utcoffset() is None:
        raise ValueError("backup timestamp must be timezone-aware")
    source_inspection = inspect_database(database_path)
    directory = backup_directory.expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise DatabaseMaintenanceError(
            f"backup destination is not a directory: {directory}"
        )
    directory.mkdir(mode=PRIVATE_DIRECTORY_MODE, parents=True, exist_ok=True)
    os.chmod(directory, PRIVATE_DIRECTORY_MODE)

    stamp = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = (
        f"solarinspector-before-schema-{target_schema_version}-{stamp}"
        f"-from-{source_inspection.current_schema_version}.db"
    )
    destination = directory / filename
    if destination.exists():
        raise DatabaseMaintenanceError(
            f"backup destination already exists: {destination}"
        )
    if destination.resolve() == source_inspection.database_path:
        raise DatabaseMaintenanceError("backup destination equals source database")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{filename}.",
        suffix=".tmp",
        dir=directory,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        os.chmod(temporary, PRIVATE_FILE_MODE)
        with (
            _read_only_connection(source_inspection.database_path) as source,
            closing(sqlite3.connect(temporary)) as target,
        ):
            source.backup(target)
            target.commit()
        temporary_inspection = inspect_database(temporary)
        _verify_backup_matches(source_inspection, temporary_inspection)
        temporary.replace(destination)
        os.chmod(destination, PRIVATE_FILE_MODE)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return DatabaseBackup(
        source_path=source_inspection.database_path,
        backup_path=destination,
        source_schema_version=source_inspection.current_schema_version,
        target_schema_version=target_schema_version,
        integrity_check=temporary_inspection.integrity_check,
        sample_count=temporary_inspection.table_counts.get("samples"),
    )


def dry_run_database_migration(
    database_path: Path,
    *,
    application_version: str,
) -> MigrationRun:
    """Apply and verify the migration only on a temporary SQLite backup.

    Args:
        database_path: Existing source database, opened read-only.
        application_version: Version recorded only in the temporary ledger.

    Returns:
        The verified plan and target result. ``backup_path`` is ``None``
        because the temporary copy is removed before return.

    Raises:
        DatabaseMaintenanceError: If source or temporary-copy checks fail.
        DatabaseSchemaError: If the schema is unsupported.
        sqlite3.DatabaseError: If migration cannot complete.

    Side Effects:
        Creates and removes a temporary directory. The source database and its
        timestamps, bytes, WAL, and migration ledger remain unchanged.
    """

    source = inspect_database(database_path)
    with tempfile.TemporaryDirectory(prefix="solarinspector-migration-dry-run-") as raw:
        temporary = Path(raw) / "database.db"
        _copy_database(source.database_path, temporary)
        with closing(sqlite3.connect(temporary)) as connection:
            applied = apply_migrations(
                connection,
                application_version=application_version,
            )
            verify_schema(connection)
            integrity = _integrity_result(connection)
        if integrity != "ok":
            raise DatabaseMaintenanceError(
                f"dry-run integrity check failed: {integrity}"
            )
        migrated = inspect_database(temporary)
        _verify_domain_counts_preserved(source, migrated)
    return MigrationRun(
        database_path=source.database_path,
        dry_run=True,
        previous_schema_version=source.current_schema_version,
        target_schema_version=get_target_version(),
        applied_migrations=applied,
        integrity_check=integrity,
        backup_path=None,
    )


def migrate_database_with_backup(
    database_path: Path,
    backup_directory: Path,
    *,
    application_version: str,
    created_at: datetime | None = None,
    backup_created: Callable[[Path], None] | None = None,
) -> MigrationRun:
    """Back up, migrate, and verify a database in a controlled sequence.

    Args:
        database_path: Existing writable database.
        backup_directory: Directory for the mandatory verified backup.
        application_version: Version recorded in the migration ledger.
        created_at: Optional timezone-aware time shared by backup and ledger.
        backup_created: Optional notification called with the verified backup
            path immediately before the source is opened writable.

    Returns:
        Applied migrations, final integrity, and persistent backup path.

    Raises:
        DatabaseMaintenanceError: If backup or post-migration verification
            fails.
        DatabaseSchemaError: If the source or target schema is incompatible.
        sqlite3.DatabaseError: If migration fails; its transaction rolls back.

    Side Effects:
        Always creates a verified backup before opening the source writable.
        Pending migrations then commit atomically. A backup remains available
        even when migration fails. This function never restores automatically.
    """

    timestamp = created_at or datetime.now(timezone.utc)
    source = inspect_database(database_path)
    backup = create_database_backup(
        source.database_path,
        backup_directory,
        target_schema_version=get_target_version(),
        created_at=timestamp,
    )
    if backup_created is not None:
        backup_created(backup.backup_path)
    try:
        with closing(sqlite3.connect(source.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            applied = apply_migrations(
                connection,
                application_version=application_version,
                applied_at=timestamp,
            )
            verify_schema(connection)
            integrity = _integrity_result(connection)
    except sqlite3.DatabaseError:
        raise
    if integrity != "ok":
        raise DatabaseMaintenanceError(
            f"post-migration integrity check failed: {integrity}"
        )
    migrated = inspect_database(source.database_path)
    _verify_domain_counts_preserved(source, migrated)
    return MigrationRun(
        database_path=source.database_path,
        dry_run=False,
        previous_schema_version=source.current_schema_version,
        target_schema_version=migrated.current_schema_version,
        applied_migrations=applied,
        integrity_check=integrity,
        backup_path=backup.backup_path,
    )


def _copy_database(source_path: Path, destination_path: Path) -> None:
    with (
        _read_only_connection(source_path) as source,
        closing(sqlite3.connect(destination_path)) as target,
    ):
        source.backup(target)
        target.commit()


def _verify_backup_matches(
    source: DatabaseInspection,
    backup: DatabaseInspection,
) -> None:
    if source.current_schema_version != backup.current_schema_version:
        raise DatabaseMaintenanceError("backup schema version differs from source")
    _verify_domain_counts_preserved(source, backup)


def _verify_domain_counts_preserved(
    before: DatabaseInspection,
    after: DatabaseInspection,
) -> None:
    for table, count in before.table_counts.items():
        if after.table_counts.get(table) != count:
            raise DatabaseMaintenanceError(
                f"row count changed unexpectedly for table {table}"
            )


def _existing_database_path(database_path: Path) -> Path:
    path = database_path.expanduser().resolve()
    if not path.exists():
        raise DatabaseMaintenanceError(f"database does not exist: {path}")
    if not path.is_file():
        raise DatabaseMaintenanceError(f"database path is not a regular file: {path}")
    return path


@contextmanager
def _read_only_connection(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        yield connection
    finally:
        connection.close()


def _integrity_result(connection: sqlite3.Connection) -> str:
    rows = connection.execute("PRAGMA integrity_check").fetchall()
    return "\n".join(str(row[0]) for row in rows)


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_schema
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
        ).fetchone()
        is not None
    )


@dataclass(frozen=True)
class RetentionPlan:
    """Describe the raw-data rows a retention cut-off would delete."""

    database_path: Path
    keep_raw_days: int
    cutoff_epoch: float
    sample_count: int
    dependent_counts: dict[str, int]

    @property
    def dependent_row_count(self) -> int:
        """Return the number of dependent rows in the plan."""
        return sum(self.dependent_counts.values())

    @property
    def total_row_count(self) -> int:
        """Return the total number of rows in the plan."""
        return self.sample_count + self.dependent_row_count


@dataclass(frozen=True)
class RetentionResult:
    """Report the rows a retention run actually deleted."""

    plan: RetentionPlan
    deleted_samples: int
    deleted_dependent_counts: dict[str, int]


def _sample_dependent_tables(connection: sqlite3.Connection) -> tuple[str, ...]:
    """Return tables that reference samples through a sample_id column."""
    names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'samples' ORDER BY name"
        )
    ]
    dependent: list[str] = []
    for name in names:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({name})")}
        if "sample_id" in columns:
            dependent.append(name)
    return tuple(dependent)


def _retention_cutoff(keep_raw_days: int, now_epoch: float | None) -> float:
    """Return the epoch before which raw samples count as expired."""
    if keep_raw_days < 1:
        raise DatabaseMaintenanceError("keep_raw_days muss mindestens 1 sein.")
    reference = time.time() if now_epoch is None else now_epoch
    return reference - keep_raw_days * 86_400.0


def plan_retention(
    database_path: Path,
    keep_raw_days: int,
    *,
    now_epoch: float | None = None,
) -> RetentionPlan:
    """Plan how many raw rows a retention rule would delete.

    Args:
        database_path: Existing SQLite database file.
        keep_raw_days: Number of days of raw samples to keep.
        now_epoch: Optional reference time for deterministic tests.

    Returns:
        Row counts per affected table. Nothing is deleted.

    Raises:
        DatabaseMaintenanceError: If the path is unusable or the input invalid.

    Side Effects:
        Opens the database read-only and runs one counting query per table.
    """
    path = _existing_database_path(database_path)
    cutoff = _retention_cutoff(keep_raw_days, now_epoch)
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
        sample_count = connection.execute(
            "SELECT COUNT(*) FROM samples WHERE ts_epoch < ?", (cutoff,)
        ).fetchone()[0]
        dependent = {
            name: connection.execute(
                "SELECT COUNT(*) FROM "
                f"{name} AS dependent "
                "JOIN samples AS s ON s.id = dependent.sample_id "
                "WHERE s.ts_epoch < ?",
                (cutoff,),
            ).fetchone()[0]
            for name in _sample_dependent_tables(connection)
        }
    return RetentionPlan(
        database_path=path,
        keep_raw_days=keep_raw_days,
        cutoff_epoch=cutoff,
        sample_count=sample_count,
        dependent_counts={name: count for name, count in dependent.items() if count},
    )


def apply_retention(
    database_path: Path,
    plan: RetentionPlan,
) -> RetentionResult:
    """Delete the rows described by a retention plan in one transaction.

    Args:
        database_path: Database file the plan was computed for.
        plan: Result of plan_retention for the same file.

    Returns:
        Deleted row counts per table.

    Raises:
        DatabaseMaintenanceError: If the path differs from the plan target.

    Side Effects:
        Deletes raw samples older than the cut-off and their dependent rows,"
        then commits. Foreign keys stay enabled, so a missed dependent table
        aborts the transaction instead of leaving orphaned rows.
    """
    path = _existing_database_path(database_path)
    if plan.database_path != path:
        raise DatabaseMaintenanceError(
            f"Der Plan gehört zu einer anderen Datenbank: {plan.database_path}"
        )
    if plan.sample_count == 0:
        return RetentionResult(
            plan=plan, deleted_samples=0, deleted_dependent_counts={}
        )

    deleted: dict[str, int] = {}
    with closing(sqlite3.connect(path, timeout=60)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with connection:
            for name in _sample_dependent_tables(connection):
                cursor = connection.execute(
                    "DELETE FROM "
                    f"{name} WHERE rowid IN ("
                    "SELECT dependent.rowid FROM "
                    f"{name} AS dependent "
                    "JOIN samples AS s ON s.id = dependent.sample_id "
                    "WHERE s.ts_epoch < ?)",
                    (plan.cutoff_epoch,),
                )
                if cursor.rowcount > 0:
                    deleted[name] = cursor.rowcount
            cursor = connection.execute(
                "DELETE FROM samples WHERE ts_epoch < ?", (plan.cutoff_epoch,)
            )
            deleted_samples = cursor.rowcount
    return RetentionResult(
        plan=plan,
        deleted_samples=deleted_samples,
        deleted_dependent_counts=deleted,
    )
