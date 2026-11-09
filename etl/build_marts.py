"""Stage 2: rebuild the analytical mart (idempotent full rebuild inside one transaction)."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg

from etl.db import run_sql_file

log = logging.getLogger(__name__)


def build_route_card(conn: psycopg.Connection, sql_dir: Path, as_of: date) -> int:
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    with conn.transaction():
        run_sql_file(conn, sql_dir / "30_route_card_build.sql", {"as_of": as_of})
        rows = conn.execute("SELECT count(*) FROM mart.mart_route_card").fetchone()[0]
        dist = dict(conn.execute(
            "SELECT reliability_level, count(*) FROM mart.mart_route_card GROUP BY 1 ORDER BY 1").fetchall())
        conn.execute(
            """INSERT INTO dq.run_log (run_id, stage, rows_loaded, details, started_at)
               VALUES (%s, 'mart_route_card', %s, %s::jsonb, %s)""",
            (f"mart-{as_of}", rows, __import__("json").dumps({"as_of": str(as_of), "reliability": dist}), started),
        )
    log.info("mart_route_card rebuilt as_of=%s: %s rows, reliability=%s, %.1fs", as_of, rows, dist,
             time.perf_counter() - t0)
    return rows
