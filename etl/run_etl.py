"""Stage 1: extract -> validate/clean -> idempotent load of a loading_date window into core + dq."""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg

from etl.db import run_sql_file

log = logging.getLogger(__name__)


def default_window(conn: psycopg.Connection) -> tuple[date, date]:
    lo, hi = conn.execute("SELECT min(loading_date), max(loading_date) FROM public.prices").fetchone()
    if lo is None:
        raise RuntimeError("public.prices is empty - nothing to load")
    return lo, hi


def init_schema(conn: psycopg.Connection, sql_dir: Path) -> None:
    with conn.transaction():
        run_sql_file(conn, sql_dir / "10_core_ddl.sql")
        run_sql_file(conn, sql_dir / "20_mart_ddl.sql")
    log.info("core / dq / mart schemas are in place")


def run_etl(conn: psycopg.Connection, sql_dir: Path, start: date, end: date, run_id: str | None = None) -> dict:
    """Atomic: either the whole window is rewritten or nothing changes. Re-running is a no-op in effect."""
    run_id = run_id or uuid.uuid4().hex[:12]
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    params = {"start": start, "end": end, "run_id": run_id}
    etl_dir = sql_dir / "etl"
    log.info("ETL run %s: window [%s .. %s]", run_id, start, end)

    with conn.transaction():
        run_sql_file(conn, etl_dir / "00_dim_city.sql")
        run_sql_file(conn, etl_dir / "01_stage.sql", params)

        cur = conn.execute((etl_dir / "06_stage_stats.sql").read_text(encoding="utf-8"))
        cols = [d.name for d in cur.description]
        stats = dict(zip(cols, cur.fetchone()))
        reasons = dict(conn.execute(
            "SELECT reason, count(*) FROM stg_prices WHERE reason IS NOT NULL GROUP BY 1 ORDER BY 1").fetchall())
        quarantined = sum(reasons.values())

        run_sql_file(conn, etl_dir / "02_delete_window.sql", params)
        run_sql_file(conn, etl_dir / "03_insert_quarantine.sql", params)
        run_sql_file(conn, etl_dir / "04_insert_fact.sql", params)
        run_sql_file(conn, etl_dir / "05_insert_bridge.sql", params)

        details = {**stats, "quarantine_by_reason": reasons}
        conn.execute(
            """INSERT INTO dq.run_log (run_id, stage, window_start, window_end, rows_read, rows_loaded,
                                       rows_quarantined, details, started_at)
               VALUES (%s, 'etl', %s, %s, %s, %s, %s, %s::jsonb, %s)""",
            (run_id, start, end, stats["rows_read"], stats["rows_clean"], quarantined, json.dumps(details), started),
        )

    log.info("ETL run %s: read=%s loaded=%s quarantined=%s %s | weight_cat filled=%s mismatch=%s | "
             "outlier-flagged kept in core=%s | %.1fs",
             run_id, stats["rows_read"], stats["rows_clean"], quarantined, reasons,
             stats["weight_cat_filled"], stats["weight_cat_mismatch"], stats["flagged_outliers"],
             time.perf_counter() - t0)
    return {"run_id": run_id, **details, "rows_quarantined": quarantined}
