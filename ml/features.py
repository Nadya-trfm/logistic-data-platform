from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

TARGET = "price_rub"

NUMERIC_FEATURES = [
    "distance", "total_weight", "total_volume",
    "origin_lat", "origin_lon", "dest_lat", "dest_lon",
    "year", "month", "dow", "doy",
    "doy_sin", "doy_cos", "month_sin", "month_cos", "dow_sin", "dow_cos",
]
CAT_FEATURES = [
    "origin_region", "destination_region", "origin_city", "destination_city",
    "body_group", "weight_category", "volume_category",
]
FEATURES = NUMERIC_FEATURES + CAT_FEATURES


FORBIDDEN = {
    "price", "price_rub", "price_orig", "price_with_vat", "price_km", "price_per_km", "price_per_ton",
    "transportation_cost", "customer_cost", "profit", "carrier_cost", "fx_rate",
    "avg_price", "min_km_price", "max_km_price", "price_group_id", "outlier_mark",
}


def assert_no_leakage(columns) -> None:
    bad = FORBIDDEN.intersection(columns)
    if bad:
        raise ValueError(f"target-leaking columns in feature set: {sorted(bad)}")


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    d = pd.to_datetime(out["loading_date"])
    out["year"] = d.dt.year
    out["month"] = d.dt.month
    out["dow"] = d.dt.dayofweek          # 0..6
    out["doy"] = d.dt.dayofyear
    for name, t, period in (("doy", out["doy"], 365.25), ("month", out["month"], 12.0), ("dow", out["dow"], 7.0)):
        out[f"{name}_sin"] = np.sin(2 * np.pi * t / period)
        out[f"{name}_cos"] = np.cos(2 * np.pi * t / period)
    assert_no_leakage(FEATURES)
    return out


@dataclass(frozen=True)
class Windows:
    train_from: date   
    test_from: date    
    as_of: date        


def make_windows(as_of: date) -> Windows:
    """train [as_of-3 months, as_of-3 weeks), test [as_of-3 weeks, as_of]. as_of=2026-10-26 ->
    train [2026-07-26, 2026-10-05), test [2026-10-05, 2026-10-26]."""
    return Windows(train_from=as_of - relativedelta(months=3), test_from=as_of - timedelta(weeks=3), as_of=as_of)


def split_time(df: pd.DataFrame, w: Windows) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    d = pd.to_datetime(df["loading_date"]).dt.date
    train = df[(d >= w.train_from) & (d < w.test_from)]
    test = df[(d >= w.test_from) & (d <= w.as_of)]
    future = df[d > w.as_of]
    return train, test, future


EXTRACT_SQL = """
select
    f.price_id,
    f.loading_date,
    f.loading_city_gcid,
    f.unloading_city_gcid,
    f.price_rub,
    f.distance,
    f.total_weight,
    f.total_volume,
    f.weight_category,
    f.volume_category,
    f.body_group_primary as body_group,
    f.outlier_mark,
    lc.city as origin_city,
    lc.region as origin_region,
    lc.latitude as origin_lat,
    lc.longitude as origin_lon,
    uc.city as destination_city,
    uc.region as destination_region,
    uc.latitude as dest_lat,
    uc.longitude as dest_lon
from core.fact_price f
inner join core.dim_city lc on lc.gc_id = f.loading_city_gcid
inner join core.dim_city uc on uc.gc_id = f.unloading_city_gcid
where
    f.is_fact = true and
    f.complex = false and
    f.price_rub > 0 and
    f.distance > 0 and
    f.loading_date >= %(from)s
order by f.price_id;
"""


def load_frame(conn, date_from: date) -> pd.DataFrame:
    cur = conn.execute(EXTRACT_SQL, {"from": date_from})
    cols = [c.name for c in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=cols)
    df["loading_date"] = pd.to_datetime(df["loading_date"])
    return add_features(df)
