"""天气相关分析：天气与日历如何影响骑行需求？"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import viz  # noqa: E402

AGG = ROOT / "data/processed/agg"
WEATHER_CSV = ROOT / "data/raw/weather_2019_0508.csv"
COND_ORDER = ["晴", "多云", "阴", "小雨", "雨", "大雨"]


def load() -> pd.DataFrame:
    hourly = pd.read_csv(AGG / "hourly_demand.csv", parse_dates=["date"])
    w = pd.read_csv(WEATHER_CSV)
    w["date_str"] = w["date"].astype(str)
    hourly["date_str"] = hourly["date"].dt.strftime("%Y-%m-%d")
    df = hourly.merge(
        w[["date_str", "hour", "temp_c", "precip_mm", "wind_kmh", "condition"]],
        on=["date_str", "hour"],
        how="left",
    )
    df["rain"] = (df["precip_mm"] > 0.2).astype(int)  # 0.2mm 以上记为"下雨"
    return df


def fig_temp_demand(df: pd.DataFrame) -> Path:
    """按温度分箱，比较工作日和周末的平峰骑行量。"""
    flat = df[(df["hour"] >= 10) & (df["hour"] <= 16)].copy()
    bins = np.arange(4, 36, 2)
    flat["temp_bin"] = pd.cut(flat["temp_c"], bins=bins)
    g = (
        flat.groupby(["temp_bin", "is_weekend"], observed=True)["rides"]
        .agg(["mean", "sem", "count"])
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    for is_we, color, label in [
        (False, "#1f77b4", "工作日"),
        (True, "#ff7f0e", "周末"),
    ]:
        sub = g[g["is_weekend"] == is_we]
        x = sub["temp_bin"].apply(lambda b: b.mid).values
        ax.plot(x, sub["mean"], "-o", ms=4, color=color, label=label)
        ax.fill_between(
            x,
            sub["mean"] - sub["sem"],
            sub["mean"] + sub["sem"],
            color=color,
            alpha=0.15,
        )
    ax.set_xlabel("温度（°C，2°C 分箱中点）")
    ax.set_ylabel("平峰时段(10–16 点)平均每小时骑行量")
    ax.set_title("图 9  温度分箱均值（阴影为正负一个均值标准误）")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    return viz.save_fig(fig, "fig09_temp_demand.png")


def fig_condition_demand(df: pd.DataFrame) -> Path:
    """天气分类 → 平峰小时平均需求。"""
    flat = df[(df["hour"] >= 10) & (df["hour"] <= 16)]
    means = flat.groupby("condition")["rides"].mean().reindex(COND_ORDER).dropna()
    counts = flat.groupby("condition").size().reindex(COND_ORDER).dropna()

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    colors = {
        "晴": "#f4b942",
        "多云": "#c9a66b",
        "阴": "#8d99ae",
        "小雨": "#5a7d9c",
        "雨": "#3a5a7c",
        "大雨": "#2b3a4a",
    }
    ax.bar(
        range(len(means)),
        means.values,
        color=[colors.get(c, "#999") for c in means.index],
        alpha=0.9,
    )
    for i, (c, v) in enumerate(zip(means.index, means.values)):
        ax.text(
            i, v * 1.01, f"{v:,.0f}\n(n={int(counts[c]):,})", ha="center", fontsize=8.5
        )
    ax.set_xticks(range(len(means)))
    ax.set_xticklabels(means.index)
    ax.set_ylabel("平峰时段平均每小时骑行量")
    ax.set_ylim(0, means.max() * 1.18)
    ax.set_title("图 10  天气分类与平均小时骑行量")
    ax.grid(axis="y", alpha=0.3)
    return viz.save_fig(fig, "fig10_condition_demand.png")


def run_regression(df: pd.DataFrame, out: Path) -> None:
    """OLS：需求 ~ 小时 + 周末 + 温度(二次) + 降水 + 风速。"""
    model = smf.ols(
        "rides ~ C(hour) + is_weekend + temp_c + I(temp_c ** 2) + rain + wind_kmh",
        data=df,
    ).fit(cov_type="HAC", cov_kwds={"maxlags": 24})

    coef = model.params
    temp_linear = coef["temp_c"]
    temp_quad = coef["I(temp_c ** 2)"]
    peak_temp = (
        -temp_linear / (2 * temp_quad) if temp_quad < 0 else np.nan
    )  # 倒 U 顶点（需求最大的温度）
    rain_effect = coef["rain"]
    wind_effect = coef["wind_kmh"]
    base = df["rides"].mean()

    lines = [
        "===== OLS 回归：天气/日历与小时骑行量的关系 =====",
        f"样本量 n={int(model.nobs)}，R²={model.rsquared:.3f}",
        f"平均每小时骑行量（基准）: {base:,.0f}",
        "",
        "条件相关系数（HAC 标准误；不作因果解释）:",
        f"  温度二次曲线：需求最大时的温度 ≈ {peak_temp:.1f}°C（倒 U 顶点）",
        f"  雨变量系数：{rain_effect:+,.0f} 次/小时，相当于全样本均值的 {rain_effect / base * 100:+.1f}%（不是降雨百分比效应）",
        f"  风速每 +1 km/h：{wind_effect:+.0f} 辆/时",
        "",
        "完整回归摘要:",
        str(model.summary()),
        "",
        "局限：观察性相关而非因果；ERA5 为全城单点天气；未纳入节假日与大型活动。",
    ]
    text = "\n".join(lines)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print("\n".join(lines[:14]))
    print(f"（完整摘要已存 {out}）")


def rain_test(df: pd.DataFrame) -> None:
    """雨日 vs 无雨日：日均骑行量检验（日降水 >2mm 记为雨日）。"""
    daily = (
        df.groupby("date_str")
        .agg(rides=("rides", "sum"), rain_mm=("precip_mm", "sum"))
        .reset_index()
    )
    daily["rainy_day"] = daily["rain_mm"] > 2
    rainy = daily.loc[daily["rainy_day"], "rides"]
    dry = daily.loc[~daily["rainy_day"], "rides"]
    u, p = stats.mannwhitneyu(rainy, dry, alternative="two-sided")
    print("\n===== 雨日 vs 无雨日：日均骑行量 =====")
    print(f"  雨日   n={len(rainy)}  日均 {rainy.mean():,.0f}")
    print(f"  无雨日 n={len(dry)}  日均 {dry.mean():,.0f}")
    print(f"  U={u:.0f}, p={p:.4g} -> {'差异显著' if p < 0.05 else '差异不显著'}")


def main() -> None:
    viz.setup_style()
    df = load()
    print(f"数据: {len(df):,} 小时, 覆盖 {df['date_str'].nunique()} 天")
    p1 = fig_temp_demand(df)
    p2 = fig_condition_demand(df)
    run_regression(df, ROOT / "output/results/regression_summary.txt")
    rain_test(df)
    print("天气分析图已保存:", p1, p2, sep="\n  - ")


if __name__ == "__main__":
    main()
