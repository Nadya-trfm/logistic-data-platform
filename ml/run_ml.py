from __future__ import annotations

import argparse
import json
import logging
from datetime import date, timedelta

from etl.config import load_settings
from etl.db import connect
from ml.features import FEATURES, TARGET, load_frame, make_windows, split_time
from ml.score import build_prediction_frame, save_metrics, save_predictions
from ml.train import regression_metrics, train_catboost, train_ridge

log = logging.getLogger("ml")
MODEL_NAME = "catboost_v1"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", type=date.fromisoformat)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = load_settings()
    as_of = args.as_of or s.as_of
    w = make_windows(as_of)
    log.info("windows: train [%s, %s)  test [%s, %s]  future > %s", w.train_from, w.test_from, w.test_from, w.as_of, w.as_of)

    with connect(s) as conn:
        df = load_frame(conn, w.train_from)
        train, test, future = split_time(df, w)
        train_fit = train[~train["outlier_mark"]]
        test_eval = test[~test["outlier_mark"]]
        log.info("rows: train=%s (clean %s) test=%s (clean %s) future=%s", len(train), len(train_fit),
                 len(test), len(test_eval), len(future))
        if len(train_fit) == 0 or len(test_eval) == 0:
            raise RuntimeError("empty train or test set - check core load and as_of")

        cb = train_catboost(train_fit, s.random_seed)
        ridge = train_ridge(train_fit)

        base = {"train_from": w.train_from, "train_to": w.test_from - timedelta(days=1),
                "test_from": w.test_from, "test_to": w.as_of}
        rows, report = [], {}
        for name, model in (("ridge_baseline", ridge), (MODEL_NAME, cb)):
            m = regression_metrics(test_eval[TARGET], model.predict(test_eval[FEATURES]))
            log.info("%-15s test: R2=%.4f MAPE=%.2f%% RMSE=%.0f RUB MAE=%.0f RUB (n=%s)", name, m["r2"],
                     m["mape_pct"], m["rmse_rub"], m["mae_rub"], len(test_eval))
            rows.append({"model_name": name, "split": "test", "n_rows": len(test_eval), **m, **base})
            report[name] = m
        save_metrics(conn, rows)

        frames = [build_prediction_frame(test, cb.predict(test[FEATURES]), "test", MODEL_NAME)]
        if len(future):
            frames.append(build_prediction_frame(future, cb.predict(future[FEATURES]), "future", MODEL_NAME))
        import pandas as pd
        n = save_predictions(conn, pd.concat(frames, ignore_index=True), MODEL_NAME)
        log.info("saved %s predictions to mart.ml_price_predictions (test=%s, future=%s)", n, len(test), len(future))

    s.artifact_dir.mkdir(parents=True, exist_ok=True)
    cb.save_model(str(s.artifact_dir / f"{MODEL_NAME}.cbm"))
    (s.artifact_dir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    imp = sorted(zip(FEATURES, cb.get_feature_importance()), key=lambda x: -x[1])[:8]
    log.info("top features: %s", ", ".join(f"{k}={v:.1f}" for k, v in imp))


if __name__ == "__main__":
    main()
