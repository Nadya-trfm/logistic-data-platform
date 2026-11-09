from datetime import date

from etl.build_marts import build_route_card
from etl.run_etl import run_etl

TEST_DAY = date(2031, 1, 15)   # far from the synthetic data, so assertions are exact


def _insert_deal(conn, pid, **kw):
    d = dict(price=50000.0, currency_code="643", distance=500.0, total_weight=20.0, total_volume=80.0,
             loading_city_gcid=1001, unloading_city_gcid=1003, nearest_rate_date=None, body_type=56,
             price_type=3, is_fact=True, complex=False, outlier_mark=False, weight_category=None)
    d.update(kw)
    conn.execute(
        """insert into public.prices (id, created_at, loading_date, end_loading_date, organization_id,
               loading_city_gcid, unloading_city_gcid, distance, total_weight, total_volume, body_type, price,
               currency_code, complex, price_type, is_fact, nearest_rate_date, outlier_mark, weight_category)
           values (%(id)s, now(), %(day)s, %(day)s, 100500, %(loading_city_gcid)s, %(unloading_city_gcid)s,
               %(distance)s, %(total_weight)s, %(total_volume)s, %(body_type)s, %(price)s, %(currency_code)s,
               %(complex)s, %(price_type)s, %(is_fact)s, %(nearest_rate_date)s, %(outlier_mark)s, %(weight_category)s)""",
        {"id": pid, "day": TEST_DAY, **d})
    conn.execute("INSERT INTO public.price_dates (price_id, price_date) VALUES (%s, %s)", (pid, TEST_DAY))


def _reasons(conn):
    return dict(conn.execute("SELECT price_id, reason_code FROM dq.dq_quarantine_prices WHERE loading_date = %s",
                             (TEST_DAY,)).fetchall())


def test_dq_rules_and_currency(conn, settings):
    rate_date, usd = conn.execute(
        "SELECT setting_date, value FROM public.exchange_rates WHERE num_code='840' ORDER BY setting_date DESC LIMIT 1").fetchone()
    _insert_deal(conn, 9000001)                                            # valid RUB
    _insert_deal(conn, 9000002, price=0.0)                                 # price = 0
    _insert_deal(conn, 9000003, price=-5.0)                                # negative
    _insert_deal(conn, 9000004, price=999.0)                               # RUB <= 1000
    _insert_deal(conn, 9000005, distance=0.0)
    _insert_deal(conn, 9000006, total_weight=-1.0)
    _insert_deal(conn, 9000007, total_volume=-1.0)
    _insert_deal(conn, 9000008, unloading_city_gcid=999999)                # not in cities
    _insert_deal(conn, 9000009, currency_code="840", price=1000.0, nearest_rate_date=rate_date)   # USD ok
    _insert_deal(conn, 9000010, currency_code="840", price=1000.0)         # USD without rate date
    _insert_deal(conn, 9000011, currency_code="978", price=1000.0, nearest_rate_date=date(1999, 1, 1))  # no such rate
    _insert_deal(conn, 9000012, loading_city_gcid=1001, unloading_city_gcid=1001)   # same city is NOT a DQ rule
    run_etl(conn, settings.sql_dir, TEST_DAY, TEST_DAY, run_id="t1")

    assert _reasons(conn) == {
        9000002: "PRICE_NONPOSITIVE", 9000003: "PRICE_NONPOSITIVE", 9000004: "RUB_PRICE_LE_1000",
        9000005: "DISTANCE_NONPOSITIVE", 9000006: "NEGATIVE_WEIGHT", 9000007: "NEGATIVE_VOLUME",
        9000008: "CITY_NOT_FOUND", 9000010: "NO_FX_RATE", 9000011: "NO_FX_RATE"}
    loaded = {r[0]: r for r in conn.execute(
        "SELECT price_id, price_rub, weight_category, volume_category FROM core.fact_price WHERE loading_date = %s",
        (TEST_DAY,)).fetchall()}
    assert set(loaded) == {9000001, 9000009, 9000012}
    assert loaded[9000009][1] == 1000.0 * usd                               
    assert loaded[9000001][2:] == ("FTL", "FTL")                            


def test_body_group_dedup_within_group(conn, settings):
    _insert_deal(conn, 9000020, body_type=56)
    conn.execute("INSERT INTO public.price_body_types (price_id, body_type_id) VALUES (9000020, 56), (9000020, 57), (9000020, 15)")
    _insert_deal(conn, 9000021, body_type=None)                              
    run_etl(conn, settings.sql_dir, TEST_DAY, TEST_DAY, run_id="t2")
    groups = conn.execute("SELECT body_group FROM core.fact_price_body_group WHERE price_id = 9000020 ORDER BY 1").fetchall()
    assert [g[0] for g in groups] == ["Борт", "Тент"]                         
    assert conn.execute("SELECT body_group FROM core.fact_price_body_group WHERE price_id = 9000021").fetchone()[0] == "Не указан"


def _snapshot(conn):
    return conn.execute(
        """SELECT (SELECT count(*) FROM core.fact_price), (SELECT round(sum(price_rub)::numeric, 2) FROM core.fact_price),
                  (SELECT count(*) FROM core.fact_price_body_group), (SELECT count(*) FROM core.fact_price_month),
                  (SELECT count(*) FROM dq.dq_quarantine_prices)""").fetchone()


def _mart_fingerprint(conn):
    return conn.execute(
        """SELECT count(*), md5(string_agg(concat_ws(',', price_month, loading_city_gcid, unloading_city_gcid, body_group,
                  weight_category, median_trip, p25_trip, p75_trip, trips_count, mom_pct, yoy_pct, reliability_level),
                  '|' ORDER BY price_month, loading_city_gcid, unloading_city_gcid, body_group, weight_category))
           FROM mart.mart_route_card""").fetchone()


def test_etl_and_mart_are_idempotent(conn, settings):
    start, end = date(2026, 9, 1), date(2026, 9, 30)
    run_etl(conn, settings.sql_dir, start, end, run_id="a")
    build_route_card(conn, settings.sql_dir, settings.as_of)
    snap1 = _snapshot(conn)
    mart1 = _mart_fingerprint(conn)
    run_etl(conn, settings.sql_dir, start, end, run_id="b")
    build_route_card(conn, settings.sql_dir, settings.as_of)
    assert _snapshot(conn) == snap1
    assert _mart_fingerprint(conn) == mart1


def test_mart_rules(conn, settings):
    run_etl(conn, settings.sql_dir, date(2023, 10, 1), date(2027, 12, 31), run_id="m")
    build_route_card(conn, settings.sql_dir, settings.as_of)
    q = lambda sql: conn.execute(sql).fetchone()[0]
    assert q("SELECT count(*) FROM mart.mart_route_card WHERE price_month > date_trunc('month', DATE '2026-10-26')") == 0
    assert q("SELECT count(*) FROM mart.mart_route_card WHERE reliability_level = 'HIGH' AND (trips_count < 30 OR carriers_count < 5 OR freshness_days > 30)") == 0
    assert q("SELECT count(*) FROM mart.mart_route_card WHERE trips_count = 1 AND cv_rate IS NOT NULL") == 0
    assert q("SELECT count(*) FROM mart.mart_route_card WHERE p25_trip > median_trip OR median_trip > p75_trip") == 0
    assert q("""SELECT count(*) FROM (
                   SELECT f.price_id, m.price_month, bg.body_group FROM core.fact_price f
                   JOIN core.fact_price_month m USING (price_id) JOIN core.fact_price_body_group bg USING (price_id)
                   GROUP BY 1, 2, 3 HAVING count(*) > 1) d""") == 0
    row = conn.execute("""SELECT price_month, loading_city_gcid, unloading_city_gcid, body_group, weight_category, trips_count
                          FROM mart.mart_route_card ORDER BY trips_count DESC LIMIT 1""").fetchone()
    manual = conn.execute(
        """SELECT count(DISTINCT f.price_id) FROM core.fact_price f
           JOIN core.fact_price_month m USING (price_id) JOIN core.fact_price_body_group bg USING (price_id)
           WHERE f.is_fact AND NOT f.complex AND NOT f.outlier_mark AND m.price_date <= %s AND m.price_month = %s
             AND f.loading_city_gcid = %s AND f.unloading_city_gcid = %s AND bg.body_group = %s AND f.weight_category = %s""",
        (settings.as_of, *row[:5])).fetchone()[0]
    assert manual == row[5]
