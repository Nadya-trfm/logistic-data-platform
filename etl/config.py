from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _date(name: str, default: date | None = None) -> date | None:
    raw = os.getenv(name)
    return date.fromisoformat(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    database_url: str
    sql_dir: Path
    artifact_dir: Path
    as_of: date            # snapshot date; the system clock is never used
    start_date: date | None
    end_date: date | None
    random_seed: int


def load_settings() -> Settings:
    url = os.getenv("DATABASE_URL")
    if not url:
        url = "postgresql://{u}:{p}@{h}:{port}/{db}".format(
            u=os.getenv("POSTGRES_USER", "postgres"),
            p=os.getenv("POSTGRES_PASSWORD", "postgres"),
            h=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            db=os.getenv("POSTGRES_DB", "deals_bigdata"),
        )
    return Settings(
        database_url=url,
        sql_dir=Path(os.getenv("SQL_DIR", REPO_ROOT / "sql")),
        artifact_dir=Path(os.getenv("ARTIFACT_DIR", REPO_ROOT / "artifacts")),
        as_of=_date("AS_OF", date(2026, 10, 26)),
        start_date=_date("START_DATE"),
        end_date=_date("END_DATE"),
        random_seed=int(os.getenv("RANDOM_SEED", "42")),
    )
