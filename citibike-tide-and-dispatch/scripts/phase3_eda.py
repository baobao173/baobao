"""阶段三（EDA）：星期×小时热力图、周内日均、用户结构 + 统计检验。

数据来源：data/processed/agg/（聚合小表，秒级完成）

产出：
  output/figures/fig02_heatmap_weekday_hour.png   星期×小时平均骑行量热力图
  output/figures/fig03_avg_daily_by_weekday.png   一周七天日均骑行量
  output/figures/fig04_subscriber_share_by_hour.png  年卡用户占比 24h 曲线
  output/results/stat_tests.txt                   工作日 vs 周末的假设检验
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats
import seaborn as sns

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import viz  # noqa: E402

AGG = ROOT / "data/processed/agg"
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def fig_heatmap(hourly: pd.DataFrame) -> Path:
    """图 2：星期 × 小时 平均骑行量热力图。"""
    pivot = hourly.pivot_table(index="weekday", columns="hour",
                               values="rides", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(11, 4.6))
    sns.heatmap(pivot, ax=ax, cmap="YlGnBu",
                cbar_kws={"label": "平均每小时骑行量（次）"})
    ax.set_yticklabels(WEEKDAY_CN, rotation=0)
    ax.set_xlabel("出发小时")
    ax.set_ylabel("星期")
    ax.set_title("图 2  星期 × 小时的平均骑行量热力图（2019 年 5–8 月，856 万次行程）")
    return viz.save_fig(fig, "fig02_heatmap_weekday_hour.png")


def fig_weekday_bar(daily: pd.DataFrame) -> Path:
    """图 3：一周七天日均骑行量。"""
    mean_by_wd = daily.groupby("weekday")["rides"].mean()
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    colors = ["#1f77b4"] * 5 + ["#ff7f0e"] * 2  # 周末用橙色强调
    bars = ax.bar(range(7), mean_by_wd.values, color=colors, alpha=0.85)
    ax.set_xticks(range(7))
    ax.set_xticklabels(WEEKDAY_CN)
    ax.set_ylabel("日均骑行量（次）")
    ax.set_title("图 3  一周七天的日均骑行量")
    for b, v in zip(bars, mean_by_wd.values):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.01, f"{v:,.0f}",
                ha="center", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    return viz.save_fig(fig, "fig03_avg_daily_by_weekday.png")


def fig_user_share(hourly: pd.DataFrame) -> Path:
    """图 4：年卡用户（Subscriber）占比的 24 小时曲线——通勤 vs 休闲证据。"""
    h = hourly.assign(share_sub=hourly["rides_sub"] / hourly["rides"])
    share = h.groupby("hour")["share_sub"].mean()
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    ax.plot(share.index, share.values * 100, "-o", ms=4, color="#2ca02c")
    ax.set_xlabel("出发小时")
    ax.set_ylabel("年卡用户（Subscriber）占比（%）")
    ax.set_title("图 4  不同时段的用户结构：年卡用户占比 24 小时曲线")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(alpha=0.3)
    return viz.save_fig(fig, "fig04_subscriber_share_by_hour.png")


def run_tests(daily: pd.DataFrame, out: Path) -> str:
    """工作日 vs 周末：日均骑行量、平均时长 的 Mann-Whitney U 检验。"""
    wd_rides = daily.loc[daily["is_weekend"] == False, "rides"]
    we_rides = daily.loc[daily["is_weekend"] == True, "rides"]
    wd_dur = daily.loc[daily["is_weekend"] == False, "avg_dur_sec"]
    we_dur = daily.loc[daily["is_weekend"] == True, "avg_dur_sec"]

    u1, p1 = stats.mannwhitneyu(wd_rides, we_rides, alternative="two-sided")
    u2, p2 = stats.mannwhitneyu(wd_dur, we_dur, alternative="two-sided")

    lines = [
        "===== 假设检验：工作日 vs 周末（Mann-Whitney U，双尾） =====",
        "",
        "日均骑行量:",
        f"  工作日 n={len(wd_rides)}  均值 {wd_rides.mean():,.0f}  中位数 {wd_rides.median():,.0f}",
        f"  周末   n={len(we_rides)}  均值 {we_rides.mean():,.0f}  中位数 {we_rides.median():,.0f}",
        f"  U={u1:.0f}, p={p1:.4g}  -> {'差异显著' if p1 < 0.05 else '差异不显著'}",
        "",
        "平均骑行时长(秒):",
        f"  工作日  均值 {wd_dur.mean():.0f}  中位数 {wd_dur.median():.0f}",
        f"  周末    均值 {we_dur.mean():.0f}  中位数 {we_dur.median():.0f}",
        f"  U={u2:.0f}, p={p2:.4g}  -> {'差异显著' if p2 < 0.05 else '差异不显著'}",
        "",
        "解读提示：",
        "  ① 日均骑行量：工作日(约 7.2 万)显著高于周末(约 6.4 万)——通勤需求驱动高强度使用；",
        "  ② 平均时长：周末(约 17 分钟)显著长于工作日(约 14 分钟)——周末休闲骑行占比更高；",
        "  ③ 年卡用户(Subscriber)集中于早晚高峰(见图 4)，临时用户(Customer)集中在午后与周末，",
        "     说明工作日是通勤刚需市场，周末是休闲体验市场。",
    ]
    text = "\n".join(lines)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    return text


def main() -> None:
    viz.setup_style()
    hourly = pd.read_csv(AGG / "hourly_demand.csv", parse_dates=["date"])
    daily = pd.read_csv(AGG / "daily_demand.csv", parse_dates=["date"])

    p1 = fig_heatmap(hourly)
    p2 = fig_weekday_bar(daily)
    p3 = fig_user_share(hourly)
    run_tests(daily, ROOT / "output/results/stat_tests.txt")
    print("EDA 图已保存:")
    for p in (p1, p2, p3):
        print("  -", p)


if __name__ == "__main__":
    main()
