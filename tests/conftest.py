import pytest
import psycopg

from etl.config import load_settings
from etl.run_etl import init_schema


@pytest.fixture(scope="session")
def settings():
    return load_settings()


@pytest.fixture()
def conn(settings):
    try:
        c = psycopg.connect(settings.database_url, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is not reachable (set DATABASE_URL / POSTGRES_* or run via docker compose)")
    init_schema(c, settings.sql_dir)
    c.commit()
    yield c
    c.rollback()
    c.close()
