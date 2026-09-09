"""根据训练期事故记录整理排查参考，测试年检查分层表现。"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from modeling import fit_history, score, load_data, FEATURES

ROOT = Path(__file__).resolve().parent.parent


def main():
    df = load_data()
    model, columns, train, test = fit_history(df)
    train["score"] = score(model, columns, train)
    test["score"] = score(model, columns, test)
    low, high = train.score.quantile([0.5, 0.8])
    test["group"] = pd.cut(
        test.score,
        [-np.inf, low, high, np.inf],
        labels=["较低", "中间", "较高"],
        right=False,
    )
    evaluation = test.groupby("group", observed=True).agg(
        n=("is_severe", "size"),
        mean_score=("score", "mean"),
        actual_ksi_rate=("is_severe", "mean"),
    )
    evaluation.to_csv(
        ROOT / "output/tables/priority_evaluation.csv", encoding="utf-8-sig"
    )
    # 只列历史真实出现且训练期至少记录 200 起事故的组合。
    ranking = (
        train.groupby(FEATURES, observed=True)
        .agg(
            n=("is_severe", "size"),
            ksi_rate=("is_severe", "mean"),
            model_score=("score", "mean"),
        )
        .reset_index()
    )
    ranking = ranking[ranking.n >= 200].sort_values("model_score", ascending=False)
    ranking.to_csv(
        ROOT / "output/tables/risk_scenario_ranking.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(
        [
            {
                "group": "较低",
                "lower": 0,
                "upper": low,
                "interpretation": "历史条件严重性较低；不代表通行安全",
            },
            {
                "group": "中间",
                "lower": low,
                "upper": high,
                "interpretation": "补充核查路段环境和事故暴露量",
            },
            {
                "group": "较高",
                "lower": high,
                "upper": 1,
                "interpretation": "作为现场排查参考；不能直接触发限行或封路",
            },
        ]
    ).to_csv(
        ROOT / "output/tables/priority_groups.csv", index=False, encoding="utf-8-sig"
    )
    mw = (
        df[df.is_motorway == 1]
        .groupby(["light", "weather"])
        .agg(n=("is_severe", "size"), ksi_rate=("is_severe", "mean"))
        .reset_index()
    )
    mw.to_csv(
        ROOT / "output/tables/motorway_risk_matrix.csv",
        index=False,
        encoding="utf-8-sig",
    )
    g = df.groupby("is_motorway").agg(
        n=("is_severe", "size"),
        mean_casualties=("number_of_casualties", "mean"),
        share_5plus_vehicles=("number_of_vehicles", lambda x: (x >= 5).mean()),
    )
    g.to_csv(ROOT / "output/tables/motorway_multi_casualty.csv")
    sns.set_theme(style="whitegrid")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    heat = mw.assign(value=mw.ksi_rate.where(mw.n >= 30) * 100).pivot(
        index="light", columns="weather", values="value"
    )
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.heatmap(
        heat,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        ax=ax,
        cbar_kws={"label": "记录事故中的严重率（%）"},
    )
    ax.set_title("Motorway 历史事故严重率（少于 30 起的组合留空）")
    ax.set_xlabel("天气")
    ax.set_ylabel("光照")
    fig.tight_layout()
    fig.savefig(ROOT / "output/figures/fig12_motorway_heatmap.png", dpi=150)
    plt.close(fig)
    print(evaluation.to_string())


if __name__ == "__main__":
    main()
