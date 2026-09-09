"""每个商品独立拟合；测试模型只用测试开始前的数据训练一次。"""

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MODELS = ["naive", "moving_average", "ridge"]


def features(y):
    x = pd.DataFrame({f"lag_{k}": y.shift(k) for k in range(1, 5)})
    past = y.shift(1)
    x["mean_4"] = past.rolling(4).mean()
    x["mean_8"] = past.rolling(8).mean()
    x["std_4"] = past.rolling(4).std()
    return x


def backtest(weekly, config):
    n = len(weekly)
    v = n - config["test_weeks"] - config["validation_weeks"]
    t = n - config["test_weeks"]
    rows = []
    for product in weekly:
        y = weekly[product].astype(float)
        x = features(y)
        for split, start, end in [("validation", v, t), ("test", t, n)]:
            valid = x.iloc[:start].notna().all(axis=1)
            estimator = make_pipeline(
                StandardScaler(), Ridge(alpha=config["ridge_alpha"])
            )
            estimator.fit(x.iloc[:start].loc[valid], y.iloc[:start].loc[valid])
            ridge = np.maximum(0, estimator.predict(x.iloc[start:end]))
            # 安全库存尺度只用该阶段开始前的销量；验证后允许重新估计。
            sigma = float(y.iloc[max(0, start - 12) : start].std())
            for j, i in enumerate(range(start, end)):
                values = [y.iloc[i - 1], y.iloc[i - 4 : i].mean(), ridge[j]]
                for model, prediction in zip(MODELS, values):
                    rows.append(
                        dict(
                            week=y.index[i],
                            product_id=product,
                            split=split,
                            model=model,
                            actual=y.iloc[i],
                            prediction=float(prediction),
                            sigma=sigma,
                        )
                    )
    return pd.DataFrame(rows)


def metrics(predictions):
    rows = []
    for keys, g in predictions.groupby(["split", "model", "product_id"]):
        error = (g.actual - g.prediction).abs()
        rows.append(
            dict(
                zip(["split", "model", "product_id"], keys),
                mae=error.mean(),
                wape=error.sum() / g.actual.sum() if g.actual.sum() else np.nan,
            )
        )
    per_product = pd.DataFrame(rows)
    rows = []
    for (split, model), g in predictions.groupby(["split", "model"]):
        error = (g.actual - g.prediction).abs()
        rows.append(
            dict(
                split=split,
                model=model,
                mae=error.mean(),
                wape=error.sum() / g.actual.sum(),
                macro_mae=per_product.query(
                    "split == @split and model == @model"
                ).mae.mean(),
            )
        )
    return pd.DataFrame(rows), per_product
