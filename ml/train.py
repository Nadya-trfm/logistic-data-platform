from __future__ import annotations

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.features import CAT_FEATURES, FEATURES, NUMERIC_FEATURES, TARGET


def regression_metrics(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "mape_pct": float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100),
        "rmse_rub": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae_rub": float(mean_absolute_error(y_true, y_pred)),
    }


def train_catboost(train: pd.DataFrame, seed: int) -> CatBoostRegressor:
    model = CatBoostRegressor(
        iterations=800, learning_rate=0.06, depth=8, loss_function="RMSE",
        random_seed=seed, thread_count=4, verbose=False, allow_writing_files=False,
    )
    model.fit(train[FEATURES], train[TARGET], cat_features=CAT_FEATURES)
    return model


def train_ridge(train: pd.DataFrame) -> Pipeline:
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), NUMERIC_FEATURES),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore"))]), CAT_FEATURES),
    ])
    pipe = Pipeline([("pre", pre), ("reg", Ridge(alpha=1.0))])
    pipe.fit(train[FEATURES], train[TARGET])
    return pipe
