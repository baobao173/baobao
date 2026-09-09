"""阶段五（预测）：用 日历 + 天气 + 历史需求 预测每小时全系统需求。

方法（教学友好、可复现、防数据泄漏）：
  1. 预测单元：全系统每小时出发量 rides；
  2. 特征：日历(hour/weekday/is_weekend) + 天气(temp/平方/雨/风) + 滞后需求
     （lag1=上一小时、lag24=昨日同时刻、lag168=上周同时刻）；
  3. 防泄漏：特征只用 t 时刻之前的信息；按时间顺序切 train/test，
     绝不打乱（TimeSeriesSplit 的含义在注释与报告里讲清）；
  4. 模型对比：朴素基线(直接沿用昨日同时刻) vs 岭回归 vs 随机森林；
  5. 评估：MAE / RMSE / R²，并把误差折算成业务语言（"每小时平均差 X 辆"）。

产出：
  output/results/model_comparison.csv     三个模型在测试集的指标
  output/results/forecast_summary.txt     结果与业务解读
  output/figures/fig11_forecast_vs_actual.png  测试集一周 预测 vs 实际
  output/figures/fig12_feature_importance.png  随机森林特征重要性 Top15

用法：
    python scripts/phase5_forecast.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import viz  # noqa: E402

AGG = ROOT / "data/processed/agg"
WEATHER_CSV = ROOT / "data/raw/weather_2019_0508.csv"

CAL_FEATS = ["hour", "weekday", "is_weekend"]
WEATHER_FEATS = ["temp_c", "temp2", "rain", "wind_kmh"]
LAG_FEATS = ["lag1", "lag24", "lag168"]
ALL_FEATS = CAL_FEATS + WEATHER_FEATS + LAG_FEATS


def load_and_featurize() -> pd.DataFrame:
    hourly = pd.read_csv(AGG / "hourly_demand.csv", parse_dates=["date"])
    w = pd.read_csv(WEATHER_CSV)
    w["date_str"] = w["date"].astype(str)
    hourly["date_str"] = hourly["date"].dt.strftime("%Y-%m-%d")
    df = hourly.merge(w[["date_str", "hour", "temp_c", "precip_mm", "wind_kmh"]],
                      on=["date_str", "hour"], how="left")
    # 严格按时间排序（时间序列建模的前提）
    df = df.sort_values(["date", "hour"]).reset_index(drop=True)

    df["temp2"] = df["temp_c"] ** 2
    df["rain"] = (df["precip_mm"] > 0.2).astype(int)
    # 滞后特征：全部来自过去，训练/预测时均可用 -> 无泄漏
    df["lag1"] = df["rides"].shift(1)
    df["lag24"] = df["rides"].shift(24)
    df["lag168"] = df["rides"].shift(168)
    df = df.dropna(subset=["lag168"]).reset_index(drop=True)  # 前 7 天无 lag168
    return df


def build_Xy(df: pd.DataFrame):
    """构造特征矩阵 X（含 one-hot 的日历变量）与目标 y。"""
    y = df["rides"].values
    dummies = pd.get_dummies(df[["hour", "weekday"]], columns=["hour", "weekday"], dtype=int)
    X = pd.concat([dummies.reset_index(drop=True),
                   df[["is_weekend"] + WEATHER_FEATS + LAG_FEATS].reset_index(drop=True)],
                  axis=1)
    return X, y, dummies.columns.tolist()


def split_time(X: pd.DataFrame, y: np.ndarray, frac: float = 0.7):
    """按时间顺序切分（不做任何 shuffle）。"""
    n = len(X)
    cut = int(n * frac)
    return (X.iloc[:cut], X.iloc[cut:], y[:cut], y[cut:])


def evaluate(name: str, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "model": name,
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": r2_score(y_true, y_pred),
    }


def main() -> None:
    viz.setup_style()
    df = load_and_featurize()
    print(f"样本: {len(df):,} 小时（前 7 天用于构造 lag168 后剔除）")
    print(f"时间范围: {df['date_str'].iloc[0]} ~ {df['date_str'].iloc[-1]}")

    X, y, dummy_cols = build_Xy(df)
    X_tr, X_te, y_tr, y_te = split_time(X, y)
    print(f"训练集 {len(X_tr):,} 小时 | 测试集 {len(X_te):,} 小时（测试集全部晚于训练集）")

    # ---------- 1. 朴素基线：直接用昨日同时刻 ----------
    # 注意：测试集行的 lag24 已经是"昨天真实值"，基线不训练任何参数
    y_base = X_te["lag24"].values
    rows = [evaluate("基线(昨日同时刻)", y_te, y_base)]

    # ---------- 2. 岭回归（特征标准化后） ----------
    scaler = StandardScaler().fit(X_tr)
    ridge = Ridge(alpha=10.0).fit(scaler.transform(X_tr), y_tr)
    rows.append(evaluate("岭回归", y_te, ridge.predict(scaler.transform(X_te))))

    # ---------- 3. 随机森林 ----------
    rf = RandomForestRegressor(
        n_estimators=300, max_depth=18, min_samples_leaf=3,
        random_state=42, n_jobs=-1)
    rf.fit(X_tr, y_tr)
    y_rf = rf.predict(X_te)
    rows.append(evaluate("随机森林", y_te, y_rf))

    comp = pd.DataFrame(rows)
    comp_out = ROOT / "output/results/model_comparison.csv"
    comp_out.parent.mkdir(parents=True, exist_ok=True)
    comp.to_csv(comp_out, index=False)
    print("\n===== 测试集模型对比 =====")
    print(comp.round(1).to_string(index=False))

    # 业务化解读：以随机森林为准
    best = comp.loc[comp["mae"].idxmin()]
    base_mae = comp.loc[0, "mae"]
    mean_y = y.mean()
    lines = [
        "===== 需求预测结果（全系统每小时出发量） =====",
        f"测试集: 最后 {len(X_te):,} 小时（时间上晚于训练集，模拟真实预测）",
        f"预测目标均值: {mean_y:,.0f} 辆/时（范围约 {y.min():,.0f}~{y.max():,.0f}）",
        "",
        "模型对比:",
    ]
    for _, r in comp.iterrows():
        lines.append(
            f"  {r['model']:<14} MAE={r['mae']:8,.0f}  RMSE={r['rmse']:8,.0f}  R²={r['r2']:.3f}")
    lines += [
        "",
        "业务解读（随机森林）：",
        f"  MAE={best['mae']:,.0f} 辆/时 ≈ 平均需求的 {best['mae'] / mean_y * 100:.1f}%",
        f"  相对朴素基线改善: {(1 - best['mae'] / base_mae) * 100:.1f}%",
        "  含义：若按预测提前备车/调度，绝大多数小时的偏差在 ±1 个 MAE 内；",
        "  深夜低需求时段绝对误差小，高峰时段绝对误差大但相对误差可控。",
    ]
    text = "\n".join(lines)
    (ROOT / "output/results/forecast_summary.txt").write_text(text, encoding="utf-8")
    print("\n" + "\n".join(lines[4:]))

    # ---------- 图 11：测试集末尾连续一周 预测 vs 实际 ----------
    n_show = 24 * 7
    y_true_last = y_te[-n_show:]
    fig, ax = plt.subplots(figsize=(12, 4.8))
    x = np.arange(n_show)
    ax.plot(x, y_true_last, "-", color="black", lw=1.6, label="实际")
    ax.plot(x, y_base[-n_show:], "--", color="#999", lw=1.1, label="基线(昨日同时刻)")
    ax.plot(x, ridge.predict(scaler.transform(X_te))[-n_show:], "-.",
            color="#1f77b4", lw=1.2, label="岭回归")
    ax.plot(x, y_rf[-n_show:], "-", color="#d62728", lw=1.4, label="随机森林")
    ax.set_xlabel("测试集最后一周（小时序号）")
    ax.set_ylabel("每小时骑行量")
    ax.set_title("图 11  测试集最后一周：三种方法的预测 vs 实际")
    ax.legend(frameon=False, ncol=4)
    ax.grid(alpha=0.3)
    p11 = viz.save_fig(fig, "fig11_forecast_vs_actual.png")

    # ---------- 图 12：随机森林特征重要性 ----------
    names = list(X.columns)
    imp = pd.Series(rf.feature_importances_, index=names).sort_values()
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    ax.barh(imp.index[-15:], imp.values[-15:], color="#2ca02c", alpha=0.85)
    ax.set_xlabel("特征重要性")
    ax.set_title("图 12  随机森林特征重要性 Top15")
    ax.grid(axis="x", alpha=0.3)
    p12 = viz.save_fig(fig, "fig12_feature_importance.png")

    print("图已保存:", p11, p12, sep="\n  - ")


if __name__ == "__main__":
    main()
