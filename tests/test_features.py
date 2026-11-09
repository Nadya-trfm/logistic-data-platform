from datetime import date

import numpy as np
import pandas as pd
import pytest

from ml.features import FEATURES, FORBIDDEN, add_features, assert_no_leakage, make_windows, split_time
from ml.score import build_prediction_frame


def test_no_forbidden_feature():
    assert not FORBIDDEN.intersection(FEATURES)
    with pytest.raises(ValueError):
        assert_no_leakage(FEATURES + ["avg_price"])


def test_windows_match_the_task():
    w = make_windows(date(2026, 10, 26))
    assert (w.train_from, w.test_from, w.as_of) == (date(2026, 7, 26), date(2026, 10, 5), date(2026, 10, 26))


def test_split_boundaries():
    days = ["2026-07-25", "2026-07-26", "2026-10-04", "2026-10-05", "2026-10-26", "2026-10-27"]
    df = pd.DataFrame({"loading_date": pd.to_datetime(days), "x": range(6)})
    train, test, future = split_time(df, make_windows(date(2026, 10, 26)))
    assert list(train["loading_date"].dt.strftime("%Y-%m-%d")) == ["2026-07-26", "2026-10-04"]
    assert list(test["loading_date"].dt.strftime("%Y-%m-%d")) == ["2026-10-05", "2026-10-26"]  # 10-05 only in test
    assert list(future["loading_date"].dt.strftime("%Y-%m-%d")) == ["2026-10-27"]


def test_cyclical_encoding_is_continuous_over_new_year():
    df = add_features(pd.DataFrame({"loading_date": pd.to_datetime(["2026-12-31", "2027-01-01"])}))
    assert abs(df["doy_sin"].iloc[0] - df["doy_sin"].iloc[1]) < 0.05
    assert abs(df["doy_cos"].iloc[0] - df["doy_cos"].iloc[1]) < 0.05
    assert np.allclose(df["month_sin"] ** 2 + df["month_cos"] ** 2, 1)


def test_future_predictions_have_null_actuals():
    df = pd.DataFrame({"price_id": [1, 2], "loading_date": pd.to_datetime(["2026-11-10", "2026-11-11"]),
                       "loading_city_gcid": [1001, 1001], "unloading_city_gcid": [1004, 1004],
                       "body_group": ["Тент", "Тент"], "outlier_mark": [False, False],
                       "price_rub": [152000.0, 150000.0]})      # source row already carries a price
    out = build_prediction_frame(df, [140000.0, 141000.0], "future", "m")
    assert out[["actual_price_rub", "abs_error_rub", "ape_pct"]].isna().all().all()
    test_out = build_prediction_frame(df, [140000.0, 141000.0], "test", "m")
    assert test_out["abs_error_rub"].iloc[0] == 12000.0
    assert round(test_out["ape_pct"].iloc[0], 3) == round(12000 / 152000 * 100, 3)
