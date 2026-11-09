
from __future__ import annotations

import argparse
import logging
from datetime import date

from etl.build_marts import build_route_card
from etl.config import load_settings
from etl.db import connect
from etl.run_etl import default_window, init_schema, run_etl


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["init", "etl", "marts", "all"])
    ap.add_argument("--start-date", type=date.fromisoformat, help="loading_date window start (default: env START_DATE or min in source)")
    ap.add_argument("--end-date", type=date.fromisoformat, help="loading_date window end (default: env END_DATE or max in source)")
    ap.add_argument("--as-of", type=date.fromisoformat, help="snapshot date (default: env AS_OF or 2026-10-26)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = load_settings()
    as_of = args.as_of or s.as_of
    with connect(s) as conn:
        if args.command in ("init", "all"):
            init_schema(conn, s.sql_dir)
        if args.command in ("etl", "all"):
            lo, hi = default_window(conn)
            run_etl(conn, s.sql_dir, args.start_date or s.start_date or lo, args.end_date or s.end_date or hi)
        if args.command in ("marts", "all"):
            build_route_card(conn, s.sql_dir, as_of)


if __name__ == "__main__":
    main()
