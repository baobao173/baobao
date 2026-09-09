"""统一风格；英文图中文字方便跨平台复现，中文解读见报告。"""

import os
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".cache/matplotlib")
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np

COLORS = {"moving_average": "#176B87", "naive": "#E58E26", "ridge": "#6A5ACD"}


def plot_all(
    root,
    weekly,
    selected,
    totals,
    contribution,
    predictions,
    scores,
    results,
    traces,
    policies,
    config,
):
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "axes.prop_cycle": plt.cycler(color=["#176B87", "#E58E26", "#6A5ACD"]),
        }
    )

    def save(name):
        plt.tight_layout()
        plt.savefig(root / f"outputs/figures/{name}.png", bbox_inches="tight")
        plt.close()

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for ax, col, label in zip(
        axes, ["quantity", "revenue"], ["Units sold", "Sales value (GBP)"]
    ):
        ax.plot(totals.index, totals[col])
        ax.set_ylabel(label)
        ax.grid(alpha=0.2)
    axes[0].set_title("UK positive sales | complete weeks")
    save("01_sales_trend")
    plt.figure(figsize=(8, 4))
    plt.plot(np.arange(1, len(contribution) + 1), contribution.cumulative_share)
    plt.axhline(0.8, color="gray", ls="--")
    plt.xlabel("Products ranked by training sales value")
    plt.ylabel("Cumulative share")
    plt.title("Sales concentration | training period")
    save("02_contribution")
    plt.figure(figsize=(8, 4))
    plt.scatter(selected["mean"], selected.cv, s=55, alpha=0.8)
    for pid, row in selected.head(3).iterrows():
        plt.annotate(
            str(pid), (row["mean"], row.cv), xytext=(5, 5), textcoords="offset points"
        )
    plt.xlabel("Mean weekly units")
    plt.ylabel("Coefficient of variation")
    plt.title("Selected products | training period")
    save("03_volatility")
    pid = str(selected.index[0])
    sample = predictions[
        (predictions.product_id == pid) & (predictions.split == "test")
    ]
    plt.figure(figsize=(10, 4))
    actual = sample[sample.model == "naive"]
    plt.plot(actual.week, actual.actual, color="#243746", lw=2, label="Actual")
    for model in ["moving_average", "ridge"]:
        g = sample[sample.model == model]
        plt.plot(g.week, g.prediction, label=model, color=COLORS[model])
    plt.legend()
    plt.ylabel("Weekly units")
    plt.title(f"Test forecasts | product {pid} (highest training sales)")
    save("04_forecast")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    test = scores[scores.split == "test"]
    for ax, metric in zip(axes, ["mae", "wape"]):
        bars = ax.bar(test.model, test[metric], color=[COLORS[m] for m in test.model])
        ax.set_title("Test " + metric.upper())
        ax.tick_params(axis="x", rotation=15)
        ax.bar_label(
            bars,
            labels=[
                f"{v:.1%}" if metric == "wape" else f"{v:.1f}" for v in test[metric]
            ],
            padding=3,
        )
        ax.set_ylim(0, test[metric].max() * 1.15)
        if metric == "wape":
            ax.yaxis.set_major_formatter(PercentFormatter(1))
    save("05_model_errors")
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for model in ["moving_average", "ridge"]:
        g = traces.query(
            "split == 'test' and product_id == @pid and lead == 0 and factor == 1 and model == @model"
        )
        axes[0].plot(g.week, g.ending, label=model, color=COLORS[model])
        axes[1].plot(g.week, g.shortage, label=model, color=COLORS[model])
    axes[0].set_title(f"Inventory path | product {pid}, L=0, k=1")
    axes[0].set_ylabel("Ending units")
    axes[1].set_ylabel("Unfilled units")
    axes[0].legend()
    save("06_inventory_path")
    plt.figure(figsize=(8, 4))
    base_penalty = config["base_penalty"]
    for model, g in results.query(
        "split == 'test' and lead == 0 and penalty == @base_penalty"
    ).groupby("model"):
        g = g.sort_values("factor")
        plt.plot(g.mean_inventory, g.fill_rate, marker="o", label=model)
    factors = ", ".join(str(k) for k in sorted(config["safety_factors"]))
    plt.legend()
    plt.gca().yaxis.set_major_formatter(PercentFormatter(1))
    plt.xlabel("Mean ending inventory per product-week")
    plt.ylabel("Unit fill rate")
    plt.title(f"Test trade-off | k = {factors} (left to right)")
    save("07_tradeoff")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for lead, ax in enumerate(axes):
        for policy, g in policies[policies.lead == lead].groupby("policy"):
            ax.plot(g.penalty, g.cost, marker="o", label=policy)
        ax.set_title(f"Lead time = {lead} week")
        ax.set_xlabel("Shortage penalty / holding cost")
        ax.legend()
    axes[0].set_ylabel("Test scenario cost (not GBP)")
    save("08_sensitivity")
