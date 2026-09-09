"""经营描述统计；分组统计只解释样本，不作因果推断。"""

import pandas as pd


def describe_business(weekly, selected, contribution, predictions):
    n80 = int((contribution.cumulative_share < 0.8).sum() + 1)
    summary = {
        "training_products": len(contribution),
        "products_for_80pct_sales": n80,
        "share_products_for_80pct_sales": n80 / len(contribution),
        "selected_sales_share": selected.revenue.sum() / contribution.revenue.sum(),
        "median_selected_cv": selected.cv.median(),
    }
    # 每个实际销量在三种预测方法中重复出现，只取一种以免重复计数。
    observed = predictions[predictions.model == "naive"]
    for split, g in observed.groupby("split"):
        summary[f"{split}_mean_units"] = g.actual.mean()
    summary["test_vs_validation_growth"] = (
        summary["test_mean_units"] / summary["validation_mean_units"] - 1
    )
    phases = []
    for split, g in observed.groupby("split"):
        phases.append(
            {
                "split": split,
                "first_week": str(g.week.min().date()),
                "last_week": str(g.week.max().date()),
                "weeks": g.week.nunique(),
                "mean_units": g.actual.mean(),
            }
        )
    return summary, pd.DataFrame(phases)
