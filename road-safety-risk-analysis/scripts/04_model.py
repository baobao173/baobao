# -*- coding: utf-8 -*-
"""
04_model.py — 逻辑回归建模：严重事故(KSI)概率
==============================================
研究问题 3：在控制其它因素后，哪些"可观测/可预警"因素独立地提高
严重伤亡(KSI)概率？各自效应多大（比值比 OR）？

方法（本科统计学/回归分析可复述）：
  1) 二元 Logistic 回归：P(KSI=1 | X) = 1 / (1 + exp(-Xβ))，
     用极大似然估计(MLE)求解，statsmodels 给出系数标准误与 Wald 检验。
  2) 比值比 OR = exp(β)，含义：其它变量不变时，该因素使严重事故
     "发生比"放大 OR 倍；同时给出 95% 置信区间。
  3) 变量选择上刻意使用"可干预/可预警"的情景变量（时段、光照、天气、
     道路类型、限速、城乡、是否高速、是否周末、涉事车辆数），
     不用深度学习等黑箱——每个系数都可以向管理者解释。

  * 说明：路面状况(干/湿/冰)与天气高度相关，为避免多重共线性，
    模型只保留天气，路面留给 EDA/单因素分析。

输出:
  output/figures/fig9_roc.png            ROC 曲线与 AUC
  output/figures/fig10_or_forest.png     比值比森林图（对数刻度）
  output/figures/fig11_risk_strata.png   风险分层：预测概率 vs 实际严重率
  output/tables/model_params.csv         系数 / OR / 95%CI / p
  output/tables/model_metrics.csv        样本量与 AUC 等
"""

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
from sklearn.model_selection import train_test_split

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


FEATURE_COLS = [
    "light", "weather", "road_type", "area", "speed_limit",
    "is_motorway", "is_weekend", "number_of_vehicles",
]


# 各分类变量显式指定的基准（参照）类：
#   light=白天、weather=晴、road_type=单幅路、area=城市
# 这样每个哑变量的 OR 含义是确定的，便于解释（不依赖 pandas 的字典序）。
CAT_BASE = {"light": "白天", "weather": "晴",
            "road_type": "单幅路", "area": "城市"}


def build_design(df: pd.DataFrame) -> tuple:
    """构造哑变量设计矩阵：先全量哑变量化，再剔除基准类。"""
    X = pd.get_dummies(df[FEATURE_COLS], columns=list(CAT_BASE), dtype=float)
    for col, base in CAT_BASE.items():
        X = X.drop(columns=[f"{col}_{base}"])
    y = df["is_severe"].astype(int).values
    return X, y


def param_table(model, X) -> pd.DataFrame:
    """把 statsmodels 结果整理成 系数/OR/95%CI/p 表。"""
    params = model.params
    conf = model.conf_int()
    pvals = model.pvalues
    tb = pd.DataFrame({
        "feature": params.index,
        "coef": params.values,
        "or_value": np.exp(params.values),
        "ci_low_or": np.exp(conf[0].values),
        "ci_high_or": np.exp(conf[1].values),
        "p_value": pvals.values,
    })
    tb = tb.sort_values("coef", ascending=False).reset_index(drop=True)
    return tb


def plot_roc(y_test, proba, path):
    fpr, tpr, _ = roc_curve(y_test, proba)
    roc_auc = auc(fpr, tpr)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(fpr, tpr, color="#c00000", lw=2,
            label=f"Logistic 回归 (AUC = {roc_auc:.3f})")
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
    tb = tb.sort_values("coef", ascending=True)  # 画图时从下往上
    ypos = np.arange(len(tb))
    fig, ax = plt.subplots(figsize=(7.5, 7))
    ax.errorbar(tb["or_value"], ypos,
                xerr=[tb["or_value"] - tb["ci_low_or"],
                      tb["ci_high_or"] - tb["or_value"]],
                fmt="o", color="#2f5597", ecolor="#8faadc",
                elinewidth=1.5, capsize=3, ms=5)
    ax.axvline(1.0, color="gray", ls="--", lw=1, label="OR = 1（无效应）")
    ax.set_yticks(ypos)
    ax.set_yticklabels(tb["feature"], fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("比值比 OR（对数刻度）；>1 表示提高严重事故概率")
    ax.set_title("图10  各因素的比值比(OR)及 95% 置信区间")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_risk_strata(y, proba, path):
    """风险分层：把预测概率按十分位分组，比较组内平均预测 vs 实际严重率。"""
    df = pd.DataFrame({"y": y, "proba": proba})
    df["bin"] = pd.qcut(df["proba"], 10, labels=False, duplicates="drop")
    g = df.groupby("bin").agg(avg_pred=("proba", "mean"),
                              actual=("y", "mean"),
                              n=("y", "size"))
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(g))
    ax.plot(x, g["avg_pred"] * 100, "o-", color="#2f5597", label="模型平均预测严重率%")
    ax.plot(x, g["actual"] * 100, "s--", color="#c00000", label="实际严重率%")
    ax.set_xticks(x)
    ax.set_xticklabels([str(i + 1) for i in x])
    ax.set_xlabel("预测概率十分位（1=最低风险组 … 10=最高风险组）")
    ax.set_ylabel("严重率 (%)")
    ax.set_title("图11  风险分层：预测概率越高，实际严重率越高（排序能力）")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    df = pd.read_csv(DATA, compression="gzip", low_memory=False)
    X, y = build_design(df)
    print(f"样本 n = {len(df):,}，特征数 = {X.shape[1]}，KSI 占比 = {y.mean()*100:.1f}%\n")

    # ---------- 1) statsmodels：全样本 MLE，用于统计推断 ----------
    Xc = sm.add_constant(X)  # 截距项
    model = sm.Logit(y, Xc).fit(disp=False)
    tb = param_table(model, X)
    tb.to_csv(TBL_DIR / "model_params.csv", index=False, encoding="utf-8-sig")

    print("== Logistic 回归系数（按效应从大到小）==")
    print("  特征                         OR     95%CI              p")
    for _, r in tb.iterrows():
        print(f"  {r['feature']:<26} {r['or_value']:>5.3f}  "
              f"({r['ci_low_or']:.3f}, {r['ci_high_or']:.3f})  "
              f"{fmt_p(r['p_value'])}")

    # ---------- 2) sklearn：分层 70/30 划分，用于评估（ROC/AUC）----------
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y)
    from sklearn.linear_model import LogisticRegression
    clf = LogisticRegression(max_iter=1000)
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:, 1]

    roc_auc = plot_roc(yte, proba, FIG_DIR / "fig9_roc.png")
    plot_or_forest(tb, FIG_DIR / "fig10_or_forest.png")
    plot_risk_strata(yte, proba, FIG_DIR / "fig11_risk_strata.png")

    pd.DataFrame({"metric": ["n_train", "n_test", "roc_auc"],
                  "value": [len(Xtr), len(Xte), round(roc_auc, 4)]}
                 ).to_csv(TBL_DIR / "model_metrics.csv", index=False,
                          encoding="utf-8-sig")

    print("\n== 模型评估 ==")
    print(f"  测试集 ROC AUC = {roc_auc:.3f}（>0.5 即有排序能力，>0.7 较好）")

    # ---------- 3) 业务解读：挑几个系数讲 ----------
    print("\n== 关键解读（控制其它因素后）==")

    def get_or(name):
        row = tb[tb["feature"] == name]
        return float(row["or_value"].iloc[0]) if len(row) else None

    for name, label in [
        ("light_夜间-无/弱照明", "夜间无照明(相对白天)"),
        ("light_夜间-有照明", "夜间有照明(相对白天)"),
        ("weather_雾", "雾天(相对晴天)"),
        ("weather_雨", "雨天(相对晴天)"),
        ("road_type_双向分隔路", "双向分隔路(相对单幅路)"),
        ("area_乡村", "乡村(相对城市)"),
        ("is_motorway", "高速公路(相对其他道路)"),
        ("is_weekend", "周末(相对工作日)"),
    ]:
        orv = get_or(name)
        if orv is not None:
            direction = "升高" if orv > 1 else "降低"
            print(f"  {label:<22} OR={orv:.3f} → 严重风险{direction} "
                  f"{abs(orv - 1) * 100:.1f}%")

    # 数值型变量的解读：限速每提高 10 mph 的累积效应
    sp = get_or("speed_limit")
    if sp is not None:
        print(f"  限速每提高 10mph(相对当前): OR={sp ** 10:.3f} "
              f"→ 严重风险{('升高' if sp > 1 else '降低')} "
              f"{abs(sp ** 10 - 1) * 100:.1f}%")
    nv = get_or("number_of_vehicles")
    if nv is not None:
        direction = "升高" if nv > 1 else "降低"
        print(f"  涉事车辆数每+1: OR={nv:.3f} → 严重风险{direction} "
              f"{abs(nv - 1) * 100:.1f}%（单车/两车碰撞更致命）")


if __name__ == "__main__":
    main()
