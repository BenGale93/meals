"""Backs up the meals SQLite database using SQLite's online backup API."""  # noqa: INP001

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich import print as echo
from sqlalchemy.engine import make_url

from meals.settings import database_url


def _database_path() -> Path:
    """Return the filesystem path of the configured SQLite database."""
    url = make_url(database_url())
    if not url.database or url.database == ":memory:":
        msg = f"DATABASE_URL is not a file database: {url}"
        raise typer.BadParameter(msg)
    return Path(url.database)


def _default_backup_dir(source: Path) -> Path:
    """Return the backup directory, defaulting to one beside the database."""
    configured = os.environ.get("BACKUP_DIR")
    return Path(configured) if configured else source.parent / "backups"


def _row_counts(path: Path) -> dict[str, int]:
    """Return the row count of every table, with the database opened read-only."""
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        tables = [row[0] for row in connection.execute("select name from sqlite_master where type = 'table'")]
        counts: dict[str, int] = {}
        for table in tables:
            query = f'select count(*) from "{table}"'  # noqa: S608 - table name comes from sqlite_master
            counts[table] = connection.execute(query).fetchone()[0]
        return counts


def main(
    dest: Annotated[Path | None, typer.Argument(help="Directory to write the backup into.")] = None,
    to: Annotated[Path | None, typer.Option("--to", help="Write the backup to this exact file.")] = None,
) -> None:
    """Write, then verify, a copy of the database."""
    source = _database_path()
    if not source.is_file():
        msg = f"No database found at {source}"
        raise typer.BadParameter(msg)
    if to is not None and to.resolve() == source.resolve():
        msg = "Refusing to back up a database over itself"
        raise typer.BadParameter(msg)

    if to is not None:
        target = to
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        target_dir = dest or _default_backup_dir(source)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{source.stem}-{datetime.now():%Y%m%d-%H%M%S}.db"

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()

    echo(f"Backed up [bold]{source}[/bold] to [bold]{target}[/bold]")
    for table, count in _row_counts(target).items():
        echo(f"  {table}: {count}")


if __name__ == "__main__":
    typer.run(main)
