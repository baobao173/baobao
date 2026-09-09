"""第一张王牌图：24 小时平均需求曲线（工作日 vs 周末）——"潮汐双峰"。

目的：
1. 验证真实数据可用（读入清洗后的 856 万行）；
2. 直观展示共享单车早晚高峰的"潮汐双峰"结构；
3. 把"每小时平均需求"摘要表落到 output/results/，供后续结论引用。

用法：
    python scripts/fig01_hourly_tide.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import viz  # noqa: E402

CLEAN_CSV = ROOT / "data/processed/trips_clean.csv.gz"
USE_COLS = ["start_time", "hour", "is_weekend"]  # 画这张图只需 3 列，减少内存


def main() -> None:
    print("读取清洗后数据 ...")
    df = pd.read_csv(CLEAN_CSV, usecols=USE_COLS, parse_dates=["start_time"])
    print(f"共 {len(df):,} 条行程，日期范围 "
          f"{df['start_time'].min():%Y-%m-%d} ~ {df['start_time'].max():%Y-%m-%d}")

    # 第一步聚合：按 (日期, 小时, 是否周末) 统计每小时总骑行量
    hourly = (
        df.assign(date=df["start_time"].dt.date)
        .groupby(["date", "hour", "is_weekend"], observed=True)
        .size()
        .rename("rides")
        .reset_index()
    )
    # 第二步聚合：工作日/周末内求平均 -> 代表"平均每个工作日/周末某小时的骑行量"
    avg = hourly.groupby(["hour", "is_weekend"], observed=True)["rides"].mean().unstack()

    out_csv = ROOT / "output/results/hourly_demand_avg.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    avg.to_csv(out_csv)
    print("已保存小时平均需求表:", out_csv)

    viz.setup_style()
    path = viz.plot_hourly_demand(df)
    print("图表已保存:", path)

    # 关键摘要（供后续 README / 复试讲解引用）
    for is_we, label in [(False, "工作日"), (True, "周末")]:
        s = avg[is_we]
        peak_hour = int(s.idxmax())
        print(f"{label}: 日均每小时均值 {s.mean():,.0f} 次；峰值出现在 {peak_hour}:00（约 {s.max():,.0f} 次/时）")


if __name__ == "__main__":
    main()
