"""历史事故条件严重性：2021–2023 拟合，2024 留出评价。"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from sklearn.metrics import auc, roc_curve
from sklearn.metrics import average_precision_score, brier_score_loss
from modeling import fit_history, score, load_data

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sns.set_theme(style="whitegrid", palette="colorblind")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data" / "processed" / "accidents_clean.csv.gz"
FIG_DIR = PROJECT_ROOT / "output" / "figures"
TBL_DIR = PROJECT_ROOT / "output" / "tables"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TBL_DIR.mkdir(parents=True, exist_ok=True)


def fmt_p(p: float) -> str:
    """p 值格式化：小于 0.001 显示为 <0.001，否则保留 4 位小数。"""
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def param_table(model, X) -> pd.DataFrame:
    """把 statsmodels 结果整理成 系数/OR/95%CI/p 表。"""
    params = model.params
    conf = model.conf_int()
    pvals = model.pvalues
    tb = pd.DataFrame(
        {
            "feature": params.index,
            "coef": params.values,
            "or_value": np.exp(params.values),
            "ci_low_or": np.exp(conf[0].values),
            "ci_high_or": np.exp(conf[1].values),
            "p_value": pvals.values,
        }
    )
    tb = tb.sort_values("coef", ascending=False).reset_index(drop=True)
    return tb


def plot_roc(y_test, proba, path):
    fpr, tpr, _ = roc_curve(y_test, proba)
    roc_auc = auc(fpr, tpr)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(
        fpr, tpr, color="#c00000", lw=2, label=f"Logistic 回归 (AUC = {roc_auc:.3f})"
    )
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="随机猜测 (AUC = 0.5)")
    ax.set_xlabel("假阳性率 (1 - 特异度)")
    ax.set_ylabel("真阳性率 (灵敏度)")
    ax.set_title("图9  严重事故(KSI)预测模型的 ROC 曲线")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return roc_auc


def plot_or_forest(tb, path):
    """比值比森林图：点 = OR，横线 = 95%CI，x 轴对数刻度。"""
    tb = tb[tb.feature != "const"].sort_values("coef", ascending=True)  # 画图时从下往上
    ypos = np.arange(len(tb))
    fig, ax = plt.subplots(figsize=(7.5, 7))
    ax.errorbar(
        tb["or_value"],
        ypos,
        xerr=[tb["or_value"] - tb["ci_low_or"], tb["ci_high_or"] - tb["or_value"]],
        fmt="o",
        color="#2f5597",
        ecolor="#8faadc",
        elinewidth=1.5,
        capsize=3,
        ms=5,
    )
    ax.axvline(1.0, color="gray", ls="--", lw=1, label="OR = 1")
    ax.set_yticks(ypos)
    ax.set_yticklabels(tb["feature"], fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("比值比 OR（对数刻度）；>1 表示严重事故条件胜算较高")
    ax.set_title("图10  各因素的比值比(OR)及 95% 置信区间")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_risk_strata(y, proba, path):
    """风险分层：把预测概率按十分位分组，比较组内平均预测 vs 实际严重率。"""
    df = pd.DataFrame({"y": y, "proba": proba})
    df["bin"] = pd.qcut(df["proba"], 10, labels=False, duplicates="drop")
    g = df.groupby("bin").agg(
        avg_pred=("proba", "mean"), actual=("y", "mean"), n=("y", "size")
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(g))
    ax.plot(x, g["avg_pred"] * 100, "o-", color="#2f5597", label="模型平均预测严重率%")
    ax.plot(x, g["actual"] * 100, "s--", color="#c00000", label="实际严重率%")
    ax.set_xticks(x)
    ax.set_xticklabels([str(i + 1) for i in x])
    ax.set_xlabel("预测概率十分位（1=最低风险组 … 10=最高风险组）")
    ax.set_ylabel("严重率 (%)")
    ax.set_title("图11  风险分层：2024 年测试集预测与实际严重率")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    df = load_data()
    model, columns, train, test = fit_history(df)
    table = param_table(model, None)
    table.to_csv(TBL_DIR / "model_params.csv", index=False, encoding="utf-8-sig")
    proba = score(model, columns, test)
    y = test.is_severe
    roc_auc = plot_roc(y, proba, FIG_DIR / "fig9_roc.png")
    plot_or_forest(table, FIG_DIR / "fig10_or_forest.png")
    plot_risk_strata(y, proba, FIG_DIR / "fig11_risk_strata.png")
    values = {
        "n_train": len(train),
        "n_test": len(test),
        "roc_auc": roc_auc,
        "average_precision": average_precision_score(y, proba),
        "test_prevalence": y.mean(),
        "brier": brier_score_loss(y, proba),
        "constant_brier": brier_score_loss(y, np.full(len(y), train.is_severe.mean())),
    }
    pd.DataFrame(values.items(), columns=["metric", "value"]).to_csv(
        TBL_DIR / "model_metrics.csv", index=False
    )
    print(pd.Series(values).to_string())


if __name__ == "__main__":
    main()
