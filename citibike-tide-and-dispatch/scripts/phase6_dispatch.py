"""阶段六（调度决策）：把"潮汐量化 + 预测"转成运营决策支持。

诚实的方法论说明
----------------
Citi Bike 官方只公开行程数据，不公开各站点的实时库存/桩位容量，
因此本项目不做"缺车次数减少了 X%"这类需要库存假设的仿真，
而是输出**可被数据直接支撑的决策支持**：

  1. 调度规模：早高峰系统净迁移量 = 每天早晚被单向搬动的车次规模（量级参考）；
  2. 调度时机：居住区/办公区两类站点的逐时净流量曲线（何时缺车、何时堆车）；
  3. 调度优先级：潮汐失衡的空间分布（是否集中在少数站点）。

口径说明：净流量 = 该小时借出 − 归还（以出发时间为准，误差 1 小时以内），
正 = 车净离开这群站点，负 = 车净流入这群站点。

数据来源：
  * data/processed/agg/station_flow.csv（站点潮汐方向与净流量）
  * data/processed/agg/daily_migration.csv（每日系统净迁移）
  * 主表（按工作日精确计算站点群逐时净流曲线）

产出：
  output/figures/fig13_dispatch_timing.png   调度时机（净流曲线）
  output/figures/fig14_dispatch_coverage.png 调度优先级覆盖曲线
  output/results/dispatch_summary.txt        决策建议与局限

用法：
    python scripts/phase6_dispatch.py
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


def load_supply_demand() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    station = pd.read_csv(AGG / "station_flow.csv")
    supply = station[station["net_morning"] > 0].sort_values("net_morning", ascending=False)
    demand = station[station["net_morning"] < 0].sort_values("net_morning")
    return station, supply, demand


def hourly_net_curves(supply: pd.DataFrame, demand: pd.DataFrame
                      ) -> tuple[pd.Series, pd.Series, int]:
    """按工作日重算两类站点的逐时净流曲线（借出−归还，除以工作日天数）。"""
    s_ids = set(supply["station_id"])
    d_ids = set(demand["station_id"])
    print("读取主表（计算调度时机曲线）...")
    df = pd.read_csv(CLEAN_CSV, usecols=["start_time", "hour", "is_weekend",
                                         "start_station_id", "end_station_id"],
                     parse_dates=["start_time"])
    wd = df[df["is_weekend"] == False]
    n_wd = wd["start_time"].dt.date.nunique()
    all_h = np.arange(24)

    # 居住型站点：借出（这些站出发的行程）与归还（回到这些站的行程）都按出发小时计数
    out_s = wd[wd["start_station_id"].isin(s_ids)].groupby("hour").size().reindex(all_h, fill_value=0)
    in_s = wd[wd["end_station_id"].isin(s_ids)].groupby("hour").size().reindex(all_h, fill_value=0)
    net_supply = (out_s - in_s).div(n_wd)

    out_d = wd[wd["start_station_id"].isin(d_ids)].groupby("hour").size().reindex(all_h, fill_value=0)
    in_d = wd[wd["end_station_id"].isin(d_ids)].groupby("hour").size().reindex(all_h, fill_value=0)
    net_demand = (out_d - in_d).div(n_wd)
    return net_supply, net_demand, n_wd


def fig_timing(net_supply: pd.Series, net_demand: pd.Series) -> Path:
    """图 13：两类站点的逐时净流曲线（正=车净离开，负=车净涌入）。"""
    fig, ax = plt.subplots(figsize=(10.5, 5))
    h = np.arange(24)
    ax.plot(h, net_supply.values, "-o", ms=4, color="#d62728",
            label="居住区站点 净流（正=车被骑走/需要补库存）")
    ax.plot(h, net_demand.values, "-o", ms=4, color="#1f77b4",
            label="办公区站点 净流（负=车涌入/桩位承压）")
    ax.axhline(0, color="gray", lw=1)
    ax.axvspan(6, 10, color="#d62728", alpha=0.06)
    ax.axvspan(17, 20, color="#1f77b4", alpha=0.06)
    ax.set_xlabel("小时")
    ax.set_ylabel("平均每小时净流量（辆/工作日）")
    ax.set_title("图 13  工作日两类站点的\"潮汐泵\"：早高峰居住区被抽空、办公区被灌满")
    ax.set_xticks(range(0, 24, 2))
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.3)
    return viz.save_fig(fig, "fig13_dispatch_timing.png")


def fig_coverage(supply: pd.DataFrame) -> Path:
    """图 14：调度优先级——按站点净借出降序的累计覆盖率。"""
    total = supply["net_morning"].sum()
    cum = supply["net_morning"].cumsum() / total
    n_stations = len(supply)

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(1, n_stations + 1)
    ax.plot(x, cum.values * 100, color="#2ca02c", lw=2)
    for k in (10, 20, 50, 100):
        v = cum.iloc[k - 1] * 100
        ax.plot(k, v, "o", color="#d62728")
        ax.annotate(f"Top{k} 站 = {v:.0f}%", (k, v),
                    textcoords="offset points", xytext=(6, -10), fontsize=9)
    ax.set_xlim(0, min(n_stations, 500))
    ax.set_xlabel("按早高峰净借出降序的站点累计数")
    ax.set_ylabel("累计覆盖率（占全部净借出%）")
    ax.set_title("图 14  潮汐失衡的空间分布：并非集中在极少数站点")
    ax.grid(alpha=0.3)
    return viz.save_fig(fig, "fig14_dispatch_coverage.png")


def main() -> None:
    viz.setup_style()
    station, supply, demand = load_supply_demand()
    print(f"站点: 总 {len(station)}，居住型(早高峰净借出) {len(supply)}，"
          f"办公型(早高峰净归还) {len(demand)}")

    mig = pd.read_csv(AGG / "daily_migration.csv")
    wd_mean = mig.loc[mig["is_weekend"] == False, "migration"].mean()
    we_mean = mig.loc[mig["is_weekend"] == True, "migration"].mean()

    net_supply, net_demand, n_wd = hourly_net_curves(supply, demand)
    p1 = fig_timing(net_supply, net_demand)
    p2 = fig_coverage(supply)

    total_pos = supply["net_morning"].sum()
    top10 = supply["net_morning"].head(10).sum() / total_pos * 100
    top20 = supply["net_morning"].head(20).sum() / total_pos * 100
    top50 = supply["net_morning"].head(50).sum() / total_pos * 100
    top100 = supply["net_morning"].head(100).sum() / total_pos * 100

    # 从净流曲线取关键时点
    morning_drain = int(net_supply.idxmax())          # 居住区车被抽走最猛的小时
    office_flood = int(net_demand.idxmin())           # 办公区车涌入最多的小时
    evening_return = int(net_supply.idxmin())         # 居住区车回流最多的小时
    office_release = int(net_demand.idxmax())         # 办公区车离开最多的小时

    lines = [
        "===== 调度决策支持摘要（2019 年 5–8 月，工作日口径） =====",
        "",
        "① 潮汐规模（量级参考）:",
        f"  早高峰系统单向净迁移：工作日日均 {wd_mean:,.0f} 辆（周末 {we_mean:,.0f} 辆），",
        "  即每天早高峰约有数千车次从居住区被单向骑往办公区。",
        "  注：系统全天总量必然自平衡（一借一还），本数字衡量的是『时空错配』的规模，",
        "      是平衡运力的量级参考，精确值需站点库存/桩位数据。",
        "",
        "② 调度时机（图 13 净流曲线）:",
        f"  居住区被抽空最猛：约 {morning_drain}:00（此时点前需确保站内库存充足，"
        f"即投放窗口宜在 {max(4, morning_drain - 2)}:00–{morning_drain - 1}:00 前后）；",
        f"  办公区被灌满最猛：约 {office_flood}:00（早高峰后桩位承压，平峰期可安排转运腾桩）；",
        f"  居住区车回流最多：约 {evening_return}:00，办公区车离开最多：约 {office_release}:00",
        "  （晚高峰后潮汐自行反向，说明总量不缺车，缺的是『正确时点、正确站点』的库存）。",
        "",
        "③ 空间分布（图 14）：",
        f"  Top 10 / 20 / 50 / 100 站分别覆盖早高峰净借出的 {top10:.0f}% / {top20:.0f}% / "
        f"{top50:.0f}% / {top100:.0f}%",
        "  —— 失衡分散在上百个站点，不能只盯少数大站；",
        "  建议：把『逐站逐时需求预测』(阶段五，MAE≈270 辆/时)作为调度分配的依据，",
        "       雨天(需求−41%)动态下调运力，晴好工作日早高峰前集中投放。",
        "",
        "④ 局限与未来工作:",
        "  - Citi Bike 官方不公开站点实时库存/桩位容量，本文给的是净流量的量级与",
        "    方向、优先级排序，不是精确仿真；",
        "  - 未来若引入库存数据，可用线性规划最小化调度成本：把本文的净迁移量/预测",
        "    需求作为约束，得到逐站逐时的派车方案；",
        "  - 站点级预测可直接在本框架上扩展（对 Top 潮汐站分别建模）。",
    ]
    text = "\n".join(lines)
    out = ROOT / "output/results/dispatch_summary.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print("图已保存:", p1, p2, sep="\n  - ")


if __name__ == "__main__":
    main()
