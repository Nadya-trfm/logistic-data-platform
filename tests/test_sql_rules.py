import pytest


@pytest.mark.parametrize("w,expected", [
    (30.0, "G20T"), (29.96, "G20T"),   
    (29.94, "FTL"), (10.0, "FTL"), (9.96, "FTL"), (9.94, "10T"), (5.0, "10T"), (4.96, "10T"),
    (4.94, "5T"), (2.5, "5T"), (2.46, "5T"), (2.44, "L5T"), (0.5, "L5T"), (0.46, "L5T"),
    (0.44, "OTH"), (0.0, "OTH"),
])
def test_weight_category(conn, w, expected):
    assert conn.execute("SELECT core.weight_category(%s::float8)", (w,)).fetchone()[0] == expected


@pytest.mark.parametrize("v,expected", [(0, "OTH"), (0.1, "FTL"), (120, "FTL"), (120.5, "OTH"), (130, "OTH")])
def test_volume_category(conn, v, expected):
    assert conn.execute("SELECT core.volume_category(%s::float8)", (v,)).fetchone()[0] == expected


@pytest.mark.parametrize("x,expected", [
    (56, "Тент"), (57, "Тент"), (61, "Тент"), (4, "Рефрижератор"), (46, "Рефрижератор"), (48, "Рефрижератор"),
    (2, "Изотерм"), (1, "Борт"), (15, "Борт"), (3, "Прочие"), (68, "Прочие"), (None, "Не указан"),
])
def test_body_group(conn, x, expected):
    assert conn.execute("SELECT core.body_group_of(%s::int)", (x,)).fetchone()[0] == expected


def test_city_dimension_is_unique_and_picks_min_id(conn, settings):
    from etl.db import run_sql_file
    run_sql_file(conn, settings.sql_dir / "etl" / "00_dim_city.sql")
    dup = conn.execute("SELECT count(*) - count(DISTINCT gc_id) FROM core.dim_city").fetchone()[0]
    assert dup == 0
    row = conn.execute("SELECT city, region, source_city_id FROM core.dim_city WHERE gc_id = 1003").fetchone()
    assert row[0] == "Казань" and row[1] == "Республика Татарстан"
    assert row[2] == conn.execute("SELECT min(id) FROM public.cities WHERE gc_id = 1003").fetchone()[0]
