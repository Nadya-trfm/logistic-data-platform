from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import psycopg

from etl.config import Settings

log = logging.getLogger(__name__)
SPLIT_RE = re.compile(r"^-- @@[ \t]*$", re.MULTILINE)  # marker must be a whole line


def connect(settings: Settings, retries: int = 30, delay: float = 2.0) -> psycopg.Connection:
    """Connect with retries (the DB container may still be initialising)."""
    last: Exception | None = None
    for _ in range(retries):
        try:
            return psycopg.connect(settings.database_url)
        except psycopg.OperationalError as exc:  # pragma: no cover - timing dependent
            last = exc
            log.warning("database not ready, retrying: %s", exc)
            time.sleep(delay)
    raise RuntimeError(f"cannot connect to database: {last}")


def run_sql_file(conn: psycopg.Connection, path: Path, params: dict | None = None) -> None:
    """Execute a .sql file. Files executed with params are split into statements on a '-- @@' line,
    because psycopg cannot run several statements in one parametrised call."""
    text = Path(path).read_text(encoding="utf-8")
    if params is None:
        conn.execute(text)
        return
    for stmt in SPLIT_RE.split(text):
        if stmt.strip():
            conn.execute(stmt, params)
