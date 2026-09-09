"""逐小时滚动预测系统借出量，所有需求和天气输入均滞后。"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import viz


def make_features(df):
    x = pd.DataFrame(index=df.index)
    for k in [1, 24, 168]:
        x[f"lag{k}"] = df.rides.shift(k)
    for col in ["temp_c", "precip_mm", "wind_kmh"]:
        x[col + "_lag1"] = df[col].shift(1)
    for col, levels in [("hour", range(24)), ("weekday", range(7))]:
        cat = pd.Categorical(df[col], categories=levels)
        dummy = pd.get_dummies(cat, prefix=col, dtype=float)
        dummy.index = x.index
        x = pd.concat([x, dummy], axis=1)
    return x


def evaluate(split, name, y, p):
    e = np.abs(np.asarray(y) - p)
    return {
        "split": split,
        "model": name,
        "mae": e.mean(),
        "rmse": np.sqrt(mean_squared_error(y, p)),
        "r2": r2_score(y, p),
        "wape": e.sum() / y.sum(),
        "test_mean": y.mean(),
    }


def main():
    viz.setup_style()
    df = pd.read_csv(ROOT / "data/processed/agg/hourly_demand.csv")
    weather = pd.read_csv(ROOT / "data/raw/weather_2019_0508.csv")
    df["date"] = pd.to_datetime(df.date).dt.strftime("%Y-%m-%d")
    weather["date"] = pd.to_datetime(weather.date).dt.strftime("%Y-%m-%d")
    df = df.merge(
        weather[["date", "hour", "temp_c", "precip_mm", "wind_kmh"]],
        on=["date", "hour"],
        validate="one_to_one",
    )
    df = df.sort_values(["date", "hour"]).reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df.date) + pd.to_timedelta(df.hour, unit="h")
    assert df.timestamp.diff().dropna().eq(pd.Timedelta(hours=1)).all()
    x = make_features(df)
    keep = x.notna().all(axis=1)
    df = df[keep]
    x = x[keep]
    y = df.rides
    val_start = int(len(df) * 0.6)
    test_start = int(len(df) * 0.8)
    rows = []
    prediction_rows = []
    last_rf = None
    for split, start, end in [
        ("validation", val_start, test_start),
        ("test", test_start, len(df)),
    ]:
        # 超参数预先固定；测试阶段允许用已经过去的验证期重新拟合。
        ridge = make_pipeline(StandardScaler(), Ridge(alpha=10))
        rf = RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        ridge.fit(x.iloc[:start], y.iloc[:start])
        rf.fit(x.iloc[:start], y.iloc[:start])
        values = {
            "昨日同时刻": x.iloc[start:end].lag24.to_numpy(),
            "岭回归": np.maximum(0, ridge.predict(x.iloc[start:end])),
            "随机森林": rf.predict(x.iloc[start:end]),
        }
        for name, pred in values.items():
            rows.append(evaluate(split, name, y.iloc[start:end], pred))
            prediction_rows.append(
                pd.DataFrame(
                    {
                        "timestamp": df.timestamp.iloc[start:end],
                        "split": split,
                        "model": name,
                        "actual": y.iloc[start:end],
                        "prediction": pred,
                    }
                )
            )
        last_rf = rf
    scores = pd.DataFrame(rows)
    selected = scores[scores.split == "validation"].sort_values("mae").iloc[0].model
    scores["selected_on_validation"] = scores.model.eq(selected)
    scores.to_csv(ROOT / "output/results/model_comparison.csv", index=False)
    pred = pd.concat(prediction_rows, ignore_index=True)
    pred.to_csv(ROOT / "output/results/forecast_predictions.csv", index=False)
    test = scores[(scores.split == "test") & (scores.model == selected)].iloc[0]
    baseline = scores[(scores.split == "test") & (scores.model == "昨日同时刻")].iloc[0]
    lines = [
        f"验证期 MAE 选择：{selected}",
        f"测试期 MAE={test.mae:.2f} 次/小时，WAPE={test.wape:.2%}，R²={test.r2:.3f}",
        f"测试误差相对昨日同时刻变化：{(test.mae/baseline.mae-1):+.1%}",
        "目标是系统总借出量，采用上一小时已完成需求及天气代理，逐小时更新输入。",
        "MAE 是平均绝对误差，不代表大多数误差位于正负 MAE 内；再分析天气不等于实时可得观测。",
    ]
    (ROOT / "output/results/forecast_summary.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    sample = pred[pred.split == "test"]
    times = sorted(sample.timestamp.unique())[-168:]
    fig, ax = plt.subplots(figsize=(12, 5))
    one = sample[sample.model == "昨日同时刻"].tail(168)
    ax.plot(one.timestamp, one.actual, color="black", label="实际")
    for name, g in sample.groupby("model"):
        g = g.tail(168)
        ax.plot(g.timestamp, g.prediction, label=name, alpha=0.8)
    ax.legend(ncol=4)
    ax.set(title="测试期最后一周：系统小时借出量", ylabel="骑行次数")
    viz.save_fig(fig, "fig11_forecast_vs_actual.png")
    imp = (
        pd.Series(last_rf.feature_importances_, index=x.columns)
        .nlargest(15)
        .sort_values()
    )
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(imp.index, imp.values)
    ax.set(title="随机森林特征重要性（不作因果解释）", xlabel="不纯度下降占比")
    viz.save_fig(fig, "fig12_feature_importance.png")
    print(scores.to_string(index=False))


if __name__ == "__main__":
    main()
