"""统一绘图风格与常用图函数。"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无界面后端，服务器/脚本环境均可出图
import matplotlib.pyplot as plt
import pandas as pd

OUT_DIR = Path(__file__).resolve().parent.parent / "output/figures"


def setup_style() -> None:
    """设置全局中文与风格参数（在 import 后、画图前调用一次）。"""
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False  # 让负号正常显示
    plt.rcParams["figure.dpi"] = 110
    plt.rcParams["savefig.dpi"] = 150
    plt.rcParams["savefig.bbox"] = "tight"


def save_fig(fig: plt.Figure, name: str) -> Path:
    """按统一命名保存到 output/figures/ 并返回路径。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_hourly_demand(
    trips: pd.DataFrame, name: str = "01_hourly_demand_weekday_weekend.png"
) -> Path:
    """图 1：一天 24 小时的平均骑行量曲线（工作日 vs 周末）。

    输入 trips 需含字段: start_time(或 date/hour)、hour、is_weekend。
    画法：先按 (日期, 小时) 统计每小时总借出，再按 工作日/周末 求平均，
    这样曲线代表"平均每个工作日/周末的某小时骑行量"，可直接比较。
    """
    if "date" not in trips.columns:
        trips = trips.assign(date=trips["start_time"].dt.date)

    hourly = (
        trips.groupby(["date", "hour", "is_weekend"], observed=True)
        .size()
        .rename("rides")
        .reset_index()
    )
    avg = (
        hourly.groupby(["hour", "is_weekend"], observed=True)["rides"].mean().unstack()
    )

    fig, ax = plt.subplots(figsize=(9, 5.5))
    labels = {False: "工作日（周一~周五）", True: "周末（周六~周日）"}
    colors = {False: "#1f77b4", True: "#ff7f0e"}
    for is_we, series in avg.items():
        ax.plot(
            series.index,
            series.values,
            "-o",
            ms=4,
            lw=2,
            color=colors[is_we],
            label=labels[is_we],
        )
    # 标注工作日早晚高峰
    for h in (8, 18):
        ax.axvline(h, color="gray", ls="--", lw=1, alpha=0.6)
    ax.set_xlabel("出发小时")
    ax.set_ylabel("平均每小时骑行量（次）")
    ax.set_title("纽约 Citi Bike 一天 24 小时的骑行需求（2019 年 5–8 月）")
    ax.set_xticks(range(0, 24, 2))
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    return save_fig(fig, name)
