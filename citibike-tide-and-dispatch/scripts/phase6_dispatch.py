"""用工作日站点净流量给出排查次序；不推算实际缺车或派车量。"""

from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import viz


def main():
    viz.setup_style()
    agg = ROOT / "data/processed/agg"
    station = pd.read_csv(agg / "station_flow.csv")
    curves = pd.read_csv(agg / "hourly_net_groups.csv")
    fig, ax = plt.subplots(figsize=(10, 5))
    for group, g in curves.groupby("group"):
        ax.plot(g.hour, g.net, marker="o", markersize=3, label=group)
    ax.axhline(0, color="gray", lw=1)
    ax.legend()
    ax.set(
        xlabel="小时",
        ylabel="平均净借出（次/工作日）",
        title="工作日站点组的借出与归还差额",
    )
    viz.save_fig(fig, "fig13_dispatch_timing.png")
    supply = (
        station[station.net_morning > 0]
        .sort_values("net_morning", ascending=False)
        .copy()
    )
    supply["cumulative_share"] = supply.net_morning.cumsum() / supply.net_morning.sum()
    supply.to_csv(ROOT / "output/results/station_priority.csv", index=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(range(1, len(supply) + 1), 100 * supply.cumulative_share)
    ax.set(
        xlabel="累计站点数",
        ylabel="累计净借出占比（%）",
        title="按早高峰净借出排序的站点覆盖率",
    )
    viz.save_fig(fig, "fig14_dispatch_coverage.png")
    text = (
        f"共有 {len(supply)} 个工作日早高峰净借出站点。前 100 个覆盖 {supply.head(100).net_morning.sum()/supply.net_morning.sum():.1%} 的净借出。\n"
        "这份排序用于确定需要优先核查库存的站点。净流量不包含初始库存、桩位容量或人工调度，不能直接换算派车数量。\n"
        "小时预测是全系统总骑行量，不能直接当作逐站预测。站点土地用途未核验，不标为居住区或办公区。"
    )
    (ROOT / "output/results/dispatch_summary.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
