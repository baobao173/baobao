"""阶段三（潮汐量化）：站点净流出分级、站点地图、每日潮汐迁移量。

数据来源：
  * data/processed/agg/station_flow.csv（站点级进出量，已含早晚高峰净流出）
  * 主表（按工作日精确重算每日系统净迁移量，供阶段六调度分析复用）
  * data/processed/agg/od_top20.csv（热门线路）

产出：
  output/figures/fig05_station_map_tide.png    站点地图（颜色=早高峰净流向）
  output/figures/fig06_top_tide_stations.png   最"潮汐"站点（供给端/需求端 Top15）
  output/figures/fig07_daily_migration.png     每日系统潮汐迁移量时间序列
  output/figures/fig08_top_od.png              最热门 20 条线路
  output/results/tide_summary.txt              潮汐量化摘要（供报告引用）
  data/processed/agg/daily_migration.csv       每日迁移量表
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import viz  # noqa: E402

AGG = ROOT / "data/processed/agg"
CLEAN_CSV = ROOT / "data/processed/trips_clean.csv.gz"
MORNING_HOURS = [7, 8, 9]


def fig_station_map(station: pd.DataFrame) -> Path:
    """图 5：站点地图。点大小=总借出量，颜色=早高峰净流出（红=净借出/居住区，蓝=净归还/办公区）。"""
    max_abs = station["net_morning"].abs().max()
    size = 30 + 120 * (np.log1p(station["rides_out"]) / np.log1p(station["rides_out"]).max())
    fig, ax = plt.subplots(figsize=(9.5, 8))
    sc = ax.scatter(station["lng"], station["lat"], c=station["net_morning"],
                    s=size, cmap="RdBu_r", vmin=-max_abs, vmax=max_abs,
                    alpha=0.8, edgecolors="none")
    cb = fig.colorbar(sc, ax=ax, shrink=0.8)
    cb.set_label("早高峰净流出 借出−归还（4 个月合计）")
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    ax.set_title("图 5  Citi Bike 站点分布与早高峰潮汐方向\n"
                 "（红=早高峰净借出/居住区，蓝=早高峰净归还/办公区，点大小=总流量）")
    return viz.save_fig(fig, "fig05_station_map_tide.png")


def fig_top_tide(station: pd.DataFrame) -> Path:
    """图 6：早高峰净流出最大（居住区）与净归还最大（办公区）的站点各 15 个。"""
    top_supply = station.nlargest(15, "net_morning")[::-1]    # 供给端：车从这里被骑走
    top_demand = station.nsmallest(15, "net_morning")[::-1]   # 需求端：车在这里堆积
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))

    for ax, data, color, title, unit in [
        (axes[0], top_supply, "#d62728",
         "早高峰净借出 Top15（车辆被骑走 → 居住区）", ""),
        (axes[1], top_demand, "#1f77b4",
         "早高峰净归还 Top15（车辆涌入 → 办公区）", ""),
    ]:
        vals = data["net_morning"].values if color.startswith("#d") else -data["net_morning"].values
        names = [str(n).replace(" & ", " &\n")[:22] for n in data["station_name"]]
        ax.barh(range(len(data)), vals, color=color, alpha=0.85)
        ax.set_yticks(range(len(data)))
        ax.set_yticklabels(names, fontsize=8)
        ax.set_title(title, fontsize=11)
        ax.grid(axis="x", alpha=0.3)
        for i, v in enumerate(vals):
            ax.text(v, i, f" {v:,.0f}", va="center", fontsize=8)

    fig.suptitle("图 6  最\"潮汐\"的站点：早高峰把车从居住区搬到办公区", fontsize=13)
    return viz.save_fig(fig, "fig06_top_tide_stations.png")


def daily_migration_from_raw() -> pd.DataFrame:
    """按日重算系统潮汐迁移量：每天早高峰各站 max(借出-归还, 0) 之和。

    含义：若系统不做任何人工调度，这些车在早高峰被单向骑走后，
    次日早高峰居住区站点至少需要同等数量的车才能满足需求（下界估计）。
    """
    print("读取主表（重算每日迁移量）...")
    df = pd.read_csv(CLEAN_CSV, usecols=["start_time", "start_station_id",
                                         "end_station_id", "hour"],
                     parse_dates=["start_time"])
    df["date"] = df["start_time"].dt.date
    m = df[df["hour"].isin(MORNING_HOURS)]
    out_s = m.groupby(["date", "start_station_id"]).size().rename("out")
    in_s = m.groupby(["date", "end_station_id"]).size().rename("in")
    net = pd.concat([out_s, in_s], axis=1).fillna(0)
    net["net"] = net["out"] - net["in"]
    pos = net[net["net"] > 0]
    daily = pos.groupby(level="date")["net"].sum().to_frame("migration")
    daily = daily.reset_index()
    dt = pd.to_datetime(daily["date"])
    daily["weekday"] = dt.dt.dayofweek
    daily["is_weekend"] = dt.dt.dayofweek >= 5
    daily.to_csv(AGG / "daily_migration.csv", index=False)
    return daily


def fig_daily_migration(daily: pd.DataFrame) -> Path:
    """图 7：每日潮汐迁移量（工作日 vs 周末）。"""
    fig, ax = plt.subplots(figsize=(11, 4.6))
    for is_we, color, label, marker in [
        (False, "#1f77b4", "工作日", "o"),
        (True, "#ff7f0e", "周末", "s"),
    ]:
        sub = daily[daily["is_weekend"] == is_we]
        ax.plot(pd.to_datetime(sub["date"]), sub["migration"],
                marker=marker, ms=3.5, lw=0, color=color, alpha=0.65, label=label)
    for is_we, color in [(False, "#1f77b4"), (True, "#ff7f0e")]:
        mean = daily.loc[daily["is_weekend"] == is_we, "migration"].mean()
        ax.axhline(mean, color=color, ls="--", lw=1.2, alpha=0.9)
    ax.set_xlabel("日期")
    ax.set_ylabel("早高峰系统潮汐迁移量（辆/日）")
    ax.set_title("图 7  每日早高峰的系统潮汐迁移量（不需要人工调度的下限估计）")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    return viz.save_fig(fig, "fig07_daily_migration.png")


def fig_top_od() -> Path:
    """图 8：最热门的 20 条线路。"""
    od = pd.read_csv(AGG / "od_top20.csv").head(15)
    fig, ax = plt.subplots(figsize=(10, 7))
    pairs = (od["start_station_name"] + "  →  " + od["end_station_name"])
    pairs = pairs.str.replace(" & ", " & ", regex=False)
    y = np.arange(len(od))[::-1]
    ax.barh(y, od["rides"], color="#9467bd", alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(pairs, fontsize=8.5)
    ax.set_xlabel("行程数（4 个月合计）")
    ax.set_title("图 8  最热门的 15 条骑行线路（含跨河通勤）")
    ax.grid(axis="x", alpha=0.3)
    return viz.save_fig(fig, "fig08_top_od.png")


def main() -> None:
    viz.setup_style()
    station = pd.read_csv(AGG / "station_flow.csv")

    p1 = fig_station_map(station)
    p2 = fig_top_tide(station)
    daily = daily_migration_from_raw()
    p3 = fig_daily_migration(daily)
    p4 = fig_top_od()

    # 摘要文本（供报告引用真实数字）
    n_station = len(station)
    types = station["tide_type"].value_counts().to_dict()
    wd_mean = daily.loc[daily["is_weekend"] == False, "migration"].mean()
    we_mean = daily.loc[daily["is_weekend"] == True, "migration"].mean()
    top_supply = station.nlargest(5, "net_morning")
    top_demand = station.nsmallest(5, "net_morning")

    lines = [
        "===== 潮汐量化摘要（2019-05-01 ~ 2019-08-31） =====",
        f"站点总数: {n_station}",
        f"站点类型: {types}",
        f"早高峰系统潮汐迁移量：工作日日均 {wd_mean:,.0f} 辆，周末日均 {we_mean:,.0f} 辆",
        "",
        "早高峰净借出 Top5（居住区，车被骑走）:",
    ]
    for _, r in top_supply.iterrows():
        lines.append(f"  {r['station_name']}: 净借出 {r['net_morning']:,.0f}")
    lines.append("早高峰净归还 Top5（办公区，车涌入）:")
    for _, r in top_demand.iterrows():
        lines.append(f"  {r['station_name']}: 净归还 {-r['net_morning']:,.0f}")
    text = "\n".join(lines)
    out = ROOT / "output/results/tide_summary.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print("图已保存:", p1, p2, p3, p4, sep="\n  - ")


if __name__ == "__main__":
    main()
