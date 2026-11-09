from __future__ import annotations

import numpy as np
import pandas as pd
import psycopg


def build_prediction_frame(df: pd.DataFrame, predicted, split: str, model_name: str) -> pd.DataFrame:
    """Fact-vs-forecast rows. For future (planned) deals the actual/error columns are NULL even if the
    source row already carries a price."""
    out = pd.DataFrame({
        "price_id": df["price_id"].to_numpy(),
        "model_name": model_name,
        "split": split,
        "loading_date": pd.to_datetime(df["loading_date"]).dt.date.to_numpy(),
        "loading_city_gcid": df["loading_city_gcid"].to_numpy(),
        "unloading_city_gcid": df["unloading_city_gcid"].to_numpy(),
        "body_group": df["body_group"].to_numpy(),
        "outlier_mark": df["outlier_mark"].to_numpy(),
        "predicted_price_rub": np.asarray(predicted, dtype=float),
    })
    if split == "future":
        actual = np.full(len(df), np.nan)
    else:
        actual = df["price_rub"].to_numpy(dtype=float)
    out["actual_price_rub"] = actual
    out["abs_error_rub"] = np.abs(actual - out["predicted_price_rub"])
    out["ape_pct"] = out["abs_error_rub"] / actual * 100
    return out


COLUMNS = ["price_id", "model_name", "split", "loading_date", "loading_city_gcid", "unloading_city_gcid",
           "body_group", "outlier_mark", "actual_price_rub", "predicted_price_rub", "abs_error_rub", "ape_pct"]


def save_predictions(conn: psycopg.Connection, frame: pd.DataFrame, model_name: str) -> int:
    """Atomic rewrite of this model's predictions (DELETE + bulk COPY) -> idempotent, no duplicates."""
    frame = frame[COLUMNS].astype(object).where(frame[COLUMNS].notna(), None)
    with conn.transaction():
        conn.execute("DELETE FROM mart.ml_price_predictions WHERE model_name = %s", (model_name,))
        with conn.cursor() as cur, cur.copy(
            f"COPY mart.ml_price_predictions ({', '.join(COLUMNS)}) FROM STDIN"
        ) as copy:
            for row in frame.itertuples(index=False, name=None):
                copy.write_row(row)
    return len(frame)


def save_metrics(conn: psycopg.Connection, rows: list[dict]) -> None:
    with conn.transaction():
        for r in rows:
            conn.execute(
                """insert into mart.ml_model_metrics (
                    model_name, split, n_rows, r2, mape_pct, rmse_rub, mae_rub,
                    train_from, train_to, test_from, test_to
                    )
                    values (
                        %(model_name)s, %(split)s, %(n_rows)s, %(r2)s, %(mape_pct)s, %(rmse_rub)s, %(mae_rub)s,
                        %(train_from)s, %(train_to)s, %(test_from)s, %(test_to)s
                    )
                     on conflict (model_name, split) do update set
                        n_rows = excluded.n_rows,
                        r2 = excluded.r2,
                        mape_pct = excluded.mape_pct,
                        rmse_rub = excluded.rmse_rub,
                        mae_rub = excluded.mae_rub,
                        train_from = excluded.train_from,
                        train_to = excluded.train_to,
                        test_from = excluded.test_from,
                        test_to = excluded.test_to,
                        trained_at = now();""", r)
