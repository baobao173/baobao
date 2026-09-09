"""阶段四（归因）：天气与日历如何影响骑行需求？

数据来源：
  * data/processed/agg/hourly_demand.csv（每小时骑行量）
  * data/raw/weather_2019_0508.csv（Open-Meteo / ERA5，纽约中央公园）

分析内容：
  1. 温度效应：温度分箱后的平均小时需求（工作日/周末分开），观察倒 U 关系；
  2. 降水效应：按天气分类对比小时需求，并做雨日 vs 无雨日统计检验；
  3. 回归模型：OLS 同时控制 小时固定效应 + 是否周末 + 温度(二次) + 降水 + 风速，
     量化"每升高 1°C / 下雨 / 大风"对需求的影响量级。

产出：
  output/figures/fig09_temp_demand.png       温度→需求（倒 U）
  output/figures/fig10_condition_demand.png  天气分类→需求
  output/results/regression_summary.txt      OLS 摘要 + 系数解读

局限（务必在报告/复试中主动说明）：本分析是观察性相关，不是因果；
ERA5 是全城单点天气，站点级差异未纳入。
"""
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
    df = hourly.merge(w[["date_str", "hour", "temp_c", "precip_mm",
                         "wind_kmh", "condition"]], on=["date_str", "hour"], how="left")
    df["rain"] = (df["precip_mm"] > 0.2).astype(int)  # 0.2mm 以上记为"下雨"
    return df


def fig_temp_demand(df: pd.DataFrame) -> Path:
    """温度→需求（平峰 10–16 点，工作日/周末分开），展示倒 U 效应。"""
    flat = df[(df["hour"] >= 10) & (df["hour"] <= 16)].copy()
    bins = np.arange(4, 36, 2)
    flat["temp_bin"] = pd.cut(flat["temp_c"], bins=bins)
    g = flat.groupby(["temp_bin", "is_weekend"], observed=True)["rides"].agg(
        ["mean", "sem", "count"]).reset_index()

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    for is_we, color, label in [(False, "#1f77b4", "工作日"), (True, "#ff7f0e", "周末")]:
        sub = g[g["is_weekend"] == is_we]
        x = sub["temp_bin"].apply(lambda b: b.mid).values
        ax.plot(x, sub["mean"], "-o", ms=4, color=color, label=label)
        ax.fill_between(x, sub["mean"] - 1.96 * sub["sem"],
                        sub["mean"] + 1.96 * sub["sem"], color=color, alpha=0.15)
    ax.axvspan(18, 28, color="green", alpha=0.06)
    ax.set_xlabel("温度（°C，2°C 分箱中点）")
    ax.set_ylabel("平峰时段(10–16 点)平均每小时骑行量")
    ax.set_title("图 9  温度与骑行需求：呈\"先升后降\"的倒 U 关系（带 95% 置信带）")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    return viz.save_fig(fig, "fig09_temp_demand.png")


def fig_condition_demand(df: pd.DataFrame) -> Path:
    """天气分类 → 平峰小时平均需求。"""
    flat = df[(df["hour"] >= 10) & (df["hour"] <= 16)]
    means = flat.groupby("condition")["rides"].mean().reindex(COND_ORDER).dropna()
    counts = flat.groupby("condition").size().reindex(COND_ORDER).dropna()

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    colors = {"晴": "#f4b942", "多云": "#c9a66b", "阴": "#8d99ae",
              "小雨": "#5a7d9c", "雨": "#3a5a7c", "大雨": "#2b3a4a"}
    ax.bar(range(len(means)), means.values,
           color=[colors.get(c, "#999") for c in means.index], alpha=0.9)
    for i, (c, v) in enumerate(zip(means.index, means.values)):
        ax.text(i, v * 1.01, f"{v:,.0f}\n(n={int(counts[c]):,})",
                ha="center", fontsize=8.5)
    ax.set_xticks(range(len(means)))
    ax.set_xticklabels(means.index)
    ax.set_ylabel("平峰时段平均每小时骑行量")
    ax.set_title("图 10  天气状况与骑行需求（雨天显著压低需求）")
    ax.grid(axis="y", alpha=0.3)
    return viz.save_fig(fig, "fig10_condition_demand.png")


def run_regression(df: pd.DataFrame, out: Path) -> None:
    """OLS：需求 ~ 小时 + 周末 + 温度(二次) + 降水 + 风速。"""
    model = smf.ols(
        "rides ~ C(hour) + is_weekend + temp_c + I(temp_c ** 2) + rain + wind_kmh",
        data=df,
    ).fit()

    coef = model.params
    temp_linear = coef["temp_c"]
    temp_quad = coef["I(temp_c ** 2)"]
    peak_temp = -temp_linear / (2 * temp_quad)  # 倒 U 顶点（需求最大的温度）
    rain_effect = coef["rain"]
    wind_effect = coef["wind_kmh"]
    base = df["rides"].mean()

    lines = [
        "===== OLS 回归：天气/日历对小时骑行量的影响 =====",
        f"样本量 n={int(model.nobs)}，R²={model.rsquared:.3f}",
        f"平均每小时骑行量（基准）: {base:,.0f}",
        "",
        "关键效应（已控制小时固定效应与是否周末）:",
        f"  温度二次曲线：需求最大时的温度 ≈ {peak_temp:.1f}°C（倒 U 顶点）",
        f"  下雨(>0.2mm/h)：平均每小时 {rain_effect:+,.0f} 辆 (约 {rain_effect / base * 100:+.1f}%)",
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
    daily = df.groupby("date_str").agg(
        rides=("rides", "sum"), rain_mm=("precip_mm", "sum")).reset_index()
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
    print("归因图已保存:", p1, p2, sep="\n  - ")


if __name__ == "__main__":
    main()
