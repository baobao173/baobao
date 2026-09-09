# -*- coding: utf-8 -*-
"""02_eda.py — 探索性数据分析 (EDA)"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无界面后端，适合脚本运行
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Windows 终端下强制 UTF-8 输出，避免中文乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------- 全局设置 ----------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data" / "processed" / "accidents_clean.csv.gz"
FIG_DIR = PROJECT_ROOT / "output" / "figures"
TBL_DIR = PROJECT_ROOT / "output" / "tables"

# 注意：必须先 set_theme 再设置中文字体，否则 seaborn 会重置 font.sans-serif
sns.set_theme(style="whitegrid", palette="colorblind")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
FIG_DIR.mkdir(parents=True, exist_ok=True)
TBL_DIR.mkdir(parents=True, exist_ok=True)

Z = 1.96  # 95% 置信区间对应的正态分位数


# ---------- 工具函数 ----------
def prop_ci(n_group: int, n_severe: int) -> tuple:
    """比例的 95% 置信区间（正态近似）：p ± 1.96*sqrt(p(1-p)/n)。

    适用前提：n*p 与 n*(1-p) 均不小于 10（本数据各分组均满足）。
    这是统计学里最常见的"大样本比例区间估计"，便于向非技术读者解释。
    """
    p = n_severe / n_group
    se = np.sqrt(p * (1 - p) / n_group)
    return max(0, p - Z * se), min(1, p + Z * se)


def group_summary(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """对某个分类变量计算 事故数/严重数/KSI率/95%CI 的汇总表。"""
    g = df.groupby(col, dropna=False)["is_severe"]
    rows = []
    for cat, idx in g.groups.items():
        sub = df.loc[idx]
        n = len(sub)
        n_sev = int(sub["is_severe"].sum())
        lo, hi = prop_ci(n, n_sev)
        rows.append(
            {
                "variable": col,
                "category": str(cat),
                "n_accidents": n,
                "n_severe": n_sev,
                "ksi_rate": n_sev / n,
                "ci_low": lo,
                "ci_high": hi,
            }
        )
    out = pd.DataFrame(rows).sort_values("ksi_rate", ascending=False)
    out["n_accidents"] = out["n_accidents"].astype(int)
    out["n_severe"] = out["n_severe"].astype(int)
    return out


# ---------- 图 1: 小时分布 ----------
def fig_hour(df):
    by_hour = (
        df.groupby("hour")
        .agg(n=("collision_index", "count"), n_severe=("is_severe", "sum"))
        .reset_index()
    )
    by_hour["rate"] = by_hour["n_severe"] / by_hour["n"]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(
        by_hour["hour"], by_hour["n"], color="#8faadc", alpha=0.85, label="事故数量"
    )
    ax1.set_xlabel("小时")
    ax1.set_ylabel("事故数量", color="#2f5597")
    ax1.set_xticks(range(0, 24))
    ax2 = ax1.twinx()
    ax2.plot(
        by_hour["hour"],
        by_hour["rate"] * 100,
        "o-",
        color="#c00000",
        lw=2,
        ms=5,
        label="KSI率(死亡+重伤)%",
    )
    ax2.set_ylabel("KSI 严重率 (%)", color="#c00000")
    ax2.set_ylim(0, 45)
    fig.suptitle("图1  记录事故数量与严重率的小时分布", fontsize=12)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig1_severity_by_hour.png", dpi=150)
    plt.close(fig)


# ---------- 图 2: 星期 x 小时 热力图 ----------
def fig_heatmap(df):
    weekday_map = {
        1: "周日",
        2: "周一",
        3: "周二",
        4: "周三",
        5: "周四",
        6: "周五",
        7: "周六",
    }
    heat = df.pivot_table(
        index="day_of_week_num",
        columns="hour",
        values="collision_index",
        aggfunc="count",
    )
    heat = heat.reindex(index=[2, 3, 4, 5, 6, 7, 1])  # 周一到周日
    heat.index = [weekday_map[d] for d in heat.index]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    sns.heatmap(heat, cmap="YlOrRd", ax=ax, cbar_kws={"label": "事故数量"})
    ax.set_title("图2  事故数量热力图（星期 × 小时）", fontsize=12)
    ax.set_xlabel("小时")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig2_heatmap_weekday_hour.png", dpi=150)
    plt.close(fig)


# ---------- 图 3: 关键风险因素（含95%CI） ----------
def bar_with_ci(ax, summ, title, xlabel, color):
    """柱状图 + 95% CI 误差线，柱顶标注严重率数值。"""
    cats = summ["category"].tolist()
    rates = (summ["ksi_rate"] * 100).tolist()
    err_lo = ((summ["ksi_rate"] - summ["ci_low"]) * 100).tolist()
    err_hi = ((summ["ci_high"] - summ["ksi_rate"]) * 100).tolist()
    err = [err_lo, err_hi]

    bars = ax.bar(
        cats,
        rates,
        yerr=err,
        capsize=4,
        color=color,
        alpha=0.9,
        error_kw={"elinewidth": 1},
    )
    ax.set_title(title, fontsize=11)
    ax.set_ylabel("KSI 严重率 (%)")
    ax.tick_params(axis="x", labelrotation=20)
    for b, r in zip(bars, rates):
        ax.text(
            b.get_x() + b.get_width() / 2, r + 0.8, f"{r:.1f}", ha="center", fontsize=8
        )


def fig_factors(df):
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    specs = [
        ("light", "按光照条件", "#4472c4"),
        ("weather", "按天气", "#ed7d31"),
        ("surface", "按路面状况", "#70ad47"),
        ("road_type", "按道路类型", "#7030a0"),
    ]
    for ax, (col, title, color) in zip(axes.ravel(), specs):
        bar_with_ci(ax, group_summary(df, col), title, col, color)
    fig.suptitle("图3  不同条件下的 KSI 严重率（含 95% 置信区间误差线）", fontsize=13)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig3_severity_by_factors.png", dpi=150)
    plt.close(fig)


# ---------- 图 4: 限速 ----------
def fig_speed(df):
    summ = group_summary(df, "speed_limit")
    summ = summ.sort_values("category", key=lambda s: s.astype(int))
    cats = summ["category"].astype(int).tolist()

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.bar(cats, summ["n_accidents"], color="#8faadc", alpha=0.8, label="事故数量")
    ax1.set_xlabel("限速 (mph)")
    ax1.set_ylabel("事故数量", color="#2f5597")
    ax2 = ax1.twinx()
    err_lo = ((summ["ksi_rate"] - summ["ci_low"]) * 100).tolist()
    err_hi = ((summ["ci_high"] - summ["ksi_rate"]) * 100).tolist()
    ax2.errorbar(
        cats,
        summ["ksi_rate"] * 100,
        yerr=[err_lo, err_hi],
        fmt="o-",
        color="#c00000",
        lw=2,
        capsize=4,
        label="KSI率%",
    )
    ax2.set_ylabel("KSI 严重率 (%)", color="#c00000")
    ax2.set_ylim(0, 45)
    fig.suptitle("图4  不同限速路段的记录事故数量与严重率", fontsize=12)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig4_severity_by_speed.png", dpi=150)
    plt.close(fig)


# ---------- 图 5: 年度趋势 ----------
def fig_trend(df):
    yearly = (
        df.groupby("year")
        .agg(n=("collision_index", "count"), n_severe=("is_severe", "sum"))
        .reset_index()
    )
    yearly["rate"] = yearly["n_severe"] / yearly["n"] * 100
    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.bar(yearly["year"], yearly["n"], color="#8faadc", label="事故数量")
    ax1.set_xlabel("年份")
    ax1.set_ylabel("事故数量", color="#2f5597")
    ax1.set_xticks(yearly["year"])
    ax2 = ax1.twinx()
    ax2.plot(
        yearly["year"], yearly["rate"], "o-", color="#c00000", lw=2, label="KSI率%"
    )
    for x, y in zip(yearly["year"], yearly["rate"]):
        ax2.annotate(
            f"{y:.1f}%",
            (x, y),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=9,
            color="#c00000",
        )
    ax2.set_ylabel("KSI 严重率 (%)", color="#c00000")
    ax2.set_ylim(0, 35)
    fig.suptitle(
        "图5  2021–2024 年记录事故数量与严重率（未作报告制度调整）", fontsize=12
    )
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig5_yearly_trend.png", dpi=150)
    plt.close(fig)


# ---------- 图 6: 高速公路专项 ----------
def fig_motorway(df):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))

    # (a) Motorway vs 其他道路
    df["road_class"] = np.where(
        df["is_motorway"] == 1, "高速公路(Motorway)", "其他道路"
    )
    summ = group_summary(df, "road_class")
    bar_with_ci(
        axes[0], summ, "(a) 高速公路 vs 其他道路 的严重率", "道路类别", "#c00000"
    )

    # (b) 高速公路内部：光照条件
    mw = df[df["is_motorway"] == 1]
    summ2 = group_summary(mw, "light")
    bar_with_ci(
        axes[1], summ2, "(b) 高速公路上：按光照条件的严重率", "光照条件", "#2f5597"
    )

    fig.suptitle("图6  Motorway 与其他道路的事故严重率", fontsize=13)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig6_motorway_focus.png", dpi=150)
    plt.close(fig)


# ---------- 图 7: 空间分布 ----------
def fig_map(df):
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, (mask, title) in zip(
        axes,
        [
            (df["is_severe"] == 0, "(a) 轻伤事故 (Slight)"),
            (df["is_severe"] == 1, "(b) 死亡/重伤事故 (KSI)"),
        ],
    ):
        sub = df[mask]
        hb = ax.hexbin(
            sub["longitude"],
            sub["latitude"],
            gridsize=80,
            bins="log",
            cmap="YlOrRd",
            mincnt=1,
        )
        ax.set_title(title)
        ax.set_xlabel("经度")
        ax.set_ylabel("纬度")
        cb = fig.colorbar(hb, ax=ax)
        cb.set_label("事故数 (log)")
    fig.suptitle("图7  英国记录事故的空间分布", fontsize=13)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig7_accident_map.png", dpi=150)
    plt.close(fig)


# ---------- 图 8: 月度 ----------
def fig_month(df):
    by_month = (
        df.groupby("month")
        .agg(n=("collision_index", "count"), n_severe=("is_severe", "sum"))
        .reset_index()
    )
    by_month["rate"] = by_month["n_severe"] / by_month["n"] * 100
    fig, ax1 = plt.subplots(figsize=(9, 4.5))
    ax1.bar(by_month["month"], by_month["n"], color="#8faadc", label="事故数量")
    ax1.set_xlabel("月份")
    ax1.set_ylabel("事故数量", color="#2f5597")
    ax1.set_xticks(range(1, 13))
    ax2 = ax1.twinx()
    ax2.plot(
        by_month["month"], by_month["rate"], "o-", color="#c00000", lw=2, label="KSI率%"
    )
    ax2.set_ylabel("KSI 严重率 (%)", color="#c00000")
    ax2.set_ylim(0, 35)
    fig.suptitle("图8  记录事故数量与严重率的月份分布", fontsize=12)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig8_severity_by_month.png", dpi=150)
    plt.close(fig)


# ---------- 主流程 ----------
def main():
    df = pd.read_csv(DATA, compression="gzip", low_memory=False)
    print(f"读取清洗后数据: {len(df):,} 起事故\n")

    print("[1/8] 图1 小时分布 ...")
    fig_hour(df)
    print("[2/8] 图2 星期x小时热力图 ...")
    fig_heatmap(df)
    print("[3/8] 图3 关键风险因素(含95%CI) ...")
    fig_factors(df)
    print("[4/8] 图4 限速 ...")
    fig_speed(df)
    print("[5/8] 图5 年度趋势 ...")
    fig_trend(df)
    print("[6/8] 图6 高速公路专项 ...")
    fig_motorway(df)
    print("[7/8] 图7 空间分布 ...")
    fig_map(df)
    print("[8/8] 图8 月度 ...")
    fig_month(df)

    # 汇总表
    tables = []
    for col in [
        "light",
        "weather",
        "surface",
        "road_type",
        "area",
        "speed_limit",
        "period",
        "is_motorway",
        "year",
    ]:
        tables.append(group_summary(df, col))
    summ_all = pd.concat(tables, ignore_index=True)
    summ_all.to_csv(TBL_DIR / "group_summary.csv", index=False, encoding="utf-8-sig")
    print(f"\n分组统计表已输出: {TBL_DIR/'group_summary.csv'}")

    # 打印几条最有业务含义的结果，便于核对
    print("\n== 关键数字速览 ==")
    for col, label in [
        ("light", "光照"),
        ("weather", "天气"),
        ("road_type", "道路"),
        ("is_motorway", "是否高速"),
    ]:
        s = group_summary(df, col)
        top = s.iloc[0]
        print(
            f"  {label}维度 最高严重率: {top['category']} = {top['ksi_rate']*100:.1f}% "
            f"(n={top['n_accidents']:,})"
        )
    print(f"\n完成: 共生成 8 张图 -> {FIG_DIR}")


if __name__ == "__main__":
    main()
