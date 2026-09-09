# -*- coding: utf-8 -*-
"""
05_decision.py — 决策支持：风险评分卡 / 高风险管理清单 / 红黄绿预警规则
=======================================================================
把第 04 步的逻辑回归转化为管理者可用的决策工具。核心思想：
  与其等事故发生后靠后车司机人工预警，不如用历史数据识别
  "什么时间、什么天气、什么路段" 严重事故概率高，从而：
    (1) 给出高风险情景清单 —— 回答"预警设施/巡查资源优先投向哪里"；
    (2) 把预测概率映射为 绿/黄/红 三档 —— 对应老爹方案里提示灯的
        工作模式（绿灯畅通、黄灯减速、红灯险情），这里给出触发阈值；
    (3) 高速公路(Motorway)专项：群死群伤特征 + 场景风险热力矩阵，
        说明为什么高速值得布设主动预警。

重要说明（写给复试老师 / 读者）：
  * 模型预测的是"一起已经发生的事故属于严重事故(KSI)的概率"，
    不是"会不会发生事故"。做实时预警仍需流量/事件数据；
    本项目用它做"条件风险排序 + 布设优先级"是合理的向下迁移。
  * 红黄绿阈值采用历史风险水平的分位数，属于演示性规则；
    实际阈值应由管理部门依据可接受风险校准。

输出:
  output/tables/risk_scenario_ranking.csv   高危情景 Top 榜单
  output/tables/motorway_risk_matrix.csv    高速(限速70)场景风险矩阵
  output/tables/motorway_multi_casualty.csv 高速 vs 其他 群死群伤对比
  output/tables/warning_rules.csv           红黄绿三档规则（含示例）
  output/figures/fig12_motorway_heatmap.png 高速场景风险热力图
"""

import itertools
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm

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

# 与 04_model.py 保持一致的变量与基准（保证评分可复现）
FEATURE_COLS = [
    "light", "weather", "road_type", "area", "speed_limit",
    "is_motorway", "is_weekend", "number_of_vehicles",
]
CAT_BASE = {"light": "白天", "weather": "晴",
            "road_type": "单幅路", "area": "城市"}


def build_design(df: pd.DataFrame) -> tuple:
    """与 04 相同的哑变量设计（显式基准类）。返回 X 与列名。"""
    X = pd.get_dummies(df[FEATURE_COLS], columns=list(CAT_BASE), dtype=float)
    for col, base in CAT_BASE.items():
        X = X.drop(columns=[f"{col}_{base}"])
    return X, X.columns.tolist()


def fit_model(df: pd.DataFrame):
    """在全部样本上重拟合与 04 同款逻辑回归，返回 (model, 设计矩阵列名)。"""
    X, cols = build_design(df)
    Xc = sm.add_constant(X)
    y = df["is_severe"].astype(int).values
    model = sm.Logit(y, Xc).fit(disp=False)
    return model, cols


def predict_scenarios(model, cols, scenarios: pd.DataFrame) -> pd.Series:
    """对情景网格预测严重事故概率（scenarios 需含 FEATURE_COLS 各列）。

    手动在首列插入常数项 1（列序 = ['const'] + 特征列，与训练一致），
    不依赖 add_constant 的自动判定，保证与模型参数(含截距)对齐。
    """
    X = pd.get_dummies(scenarios[FEATURE_COLS],
                       columns=list(CAT_BASE), dtype=float)
    # 补全缺失的哑变量列并保持与训练一致顺序
    X = X.reindex(columns=cols, fill_value=0.0)
    X.insert(0, "const", 1.0)  # 截距项
    return model.predict(X)


def main():
    df = pd.read_csv(DATA, compression="gzip", low_memory=False)
    model, cols = fit_model(df)
    print(f"模型拟合完成（n={len(df):,}），开始生成决策清单...\n")

    # ---------- 1) 高危情景 Top 榜单 ----------
    # 典型情景网格：涉事车辆数固定为 2、工作日。
    # 限速组合按英国现实约束（道路类型 → 允许限速、城乡）生成，
    # 避免出现现实中不存在的组合（如乡村单幅路 70mph）。
    speed_by_road = {
        "单幅路": [30, 40, 50, 60],       # 乡村单幅路国家限速 60mph
        "双向分隔路": [40, 50, 60, 70],    # 部分 A 级双车道可达 70mph
        "环岛": [20, 30, 40],
        "匝道": [30, 40, 50],
        "单行路": [20, 30],
    }
    areas_by_road = {
        "单幅路": ["城市", "乡村"],
        "双向分隔路": ["城市", "乡村"],
        "环岛": ["城市"],
        "匝道": ["城市"],
        "单行路": ["城市"],
    }
    grid = []
    for light, weather, road_type in itertools.product(
        ["白天", "夜间-有照明", "夜间-无/弱照明"],  # 光照
        ["晴", "雨", "雪", "雾"],                 # 天气
        list(speed_by_road),                      # 道路类型
    ):
        for area in areas_by_road[road_type]:
            for speed in speed_by_road[road_type]:
                # 高速(motorway)单独处理：双向分隔路 + 70mph
                grid.append({
                    "light": light, "weather": weather, "road_type": road_type,
                    "area": area, "speed_limit": speed, "is_motorway": 0,
                    "is_weekend": 0, "number_of_vehicles": 2,
                })
    scenarios = pd.DataFrame(grid)
    scenarios["p_severe"] = predict_scenarios(model, cols, scenarios)

    top = scenarios.sort_values("p_severe", ascending=False).head(20)
    top_out = top.copy()
    top_out["p_severe_pct"] = (top_out["p_severe"] * 100).round(2)
    top_out = top_out.drop(columns=["p_severe", "number_of_vehicles", "is_weekend"])
    top_out.to_csv(TBL_DIR / "risk_scenario_ranking.csv",
                   index=False, encoding="utf-8-sig")

    print("== 高危情景 Top 10（两车、工作日；按严重事故概率排序）==")
    for _, r in top.head(10).iterrows():
        label = "高速" if r["is_motorway"] == 1 else "普通路"
        print(f"  P={r['p_severe']*100:5.1f}%  {r['light']}/{r['weather']}  "
              f"{r['road_type']}({label}, {r['area']}, {r['speed_limit']}mph)")

    # ---------- 2) 高速公路专项场景矩阵 ----------
    mw_grid = []
    for light, weather, weekend in itertools.product(
        ["白天", "夜间-有照明", "夜间-无/弱照明"],
        ["晴", "雨", "雪", "雾"],
        [0, 1],
    ):
        mw_grid.append({
            "light": light, "weather": weather,
            "road_type": "双向分隔路", "area": "乡村",
            "speed_limit": 70, "is_motorway": 1,
            "is_weekend": weekend, "number_of_vehicles": 2,
        })
    mw = pd.DataFrame(mw_grid)
    mw["p_severe"] = predict_scenarios(model, cols, mw)
    mw_out = mw.drop(columns=["road_type", "area", "speed_limit",
                              "is_motorway", "number_of_vehicles"])
    mw_out["p_severe_pct"] = (mw_out.pop("p_severe") * 100).round(2)
    mw_out.to_csv(TBL_DIR / "motorway_risk_matrix.csv",
                  index=False, encoding="utf-8-sig")

    # 热力图（工作日，light x weather）
    heat = mw[mw["is_weekend"] == 0].pivot(
        index="light", columns="weather", values="p_severe") * 100
    heat = heat.reindex(index=["白天", "夜间-有照明", "夜间-无/弱照明"],
                        columns=["晴", "雨", "雪", "雾"])
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.heatmap(heat, annot=True, fmt=".1f", cmap="YlOrRd",
                cbar_kws={"label": "严重事故概率 (%)"}, ax=ax)
    ax.set_title("图12  高速公路上不同 光照×天气 情景的严重事故概率 (%)")
    ax.set_xlabel("天气"); ax.set_ylabel("光照")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig12_motorway_heatmap.png", dpi=150)
    plt.close(fig)

    # ---------- 3) 高速公路 群死群伤 特征 ----------
    mw_flag = np.where(df["is_motorway"] == 1, "高速", "其他道路")
    g = df.groupby(mw_flag).agg(
        事故数=("collision_index", "count"),
        平均伤亡=("number_of_casualties", "mean"),
        平均涉车数=("number_of_vehicles", "mean"),
        多车连环占比=("number_of_vehicles", lambda s: (s >= 5).mean()),
        多人伤亡占比=("number_of_casualties", lambda s: (s >= 3).mean()),
    ).round(4)
    g.to_csv(TBL_DIR / "motorway_multi_casualty.csv", encoding="utf-8-sig")
    print("\n== 高速 vs 其他道路：单起事故的'规模'特征 ==")
    print(g.to_string())

    # ---------- 4) 红黄绿三档预警规则 ----------
    # 以全部网格情景预测概率的分位数为界：p80 以上=红灯级，p50-p80=黄灯级
    p_all = scenarios["p_severe"]
    thr_red = float(p_all.quantile(0.80))
    thr_yellow = float(p_all.quantile(0.50))
    print(f"\n== 红黄绿三档规则（按情景风险分位数）==")
    print(f"  红灯级阈值: P(KSI) ≥ {thr_red*100:.1f}%  "
          f"(风险最高的 {100-80}% 情景)")
    print(f"  黄灯级阈值: {thr_yellow*100:.1f}% ≤ P(KSI) < {thr_red*100:.1f}%")
    print(f"  绿灯级:     P(KSI) < {thr_yellow*100:.1f}%")

    def level(p):
        if p >= thr_red:
            return "红灯级"
        if p >= thr_yellow:
            return "黄灯级"
        return "绿灯级"

    rules = scenarios.copy()
    rules["预警等级"] = rules["p_severe"].map(level)
    # 每一档挑一个代表情景作为示例（每组取 p_severe 最大的行）
    examples = rules.loc[rules.groupby("预警等级")["p_severe"].idxmax()]
    example_rows = []
    for lv in ["绿灯级", "黄灯级", "红灯级"]:
        if lv in examples["预警等级"].values:
            ex = examples[examples["预警等级"] == lv].iloc[0]
            example_rows.append({
                "level": lv,
                "threshold": f"P<{thr_yellow*100:.0f}%" if lv == "绿灯级"
                             else (f"{thr_yellow*100:.0f}%≤P<{thr_red*100:.0f}%"
                                   if lv == "黄灯级" else f"P≥{thr_red*100:.0f}%"),
                "typical_scenario": (
                    f"{ex['light']}+{ex['weather']}+"
                    f"{'高速' if ex['is_motorway'] else ex['road_type']}"
                    f"({ex['area']},{ex['speed_limit']}mph)"),
                "p_severe_pct": round(ex["p_severe"] * 100, 1),
                "suggested_action": {
                    "绿灯级": "正常通行，提示灯保持绿色",
                    "黄灯级": "黄灯减速提示：限速/保持车距广播，主动提示系统启动",
                    "红灯级": "红灯停止提示：建议管制/分流/封闭，配套巡查与应急值守",
                }[lv],
            })
    pd.DataFrame(example_rows).to_csv(TBL_DIR / "warning_rules.csv",
                                      index=False, encoding="utf-8-sig")
    for r in example_rows:
        print(f"  [{r['level']}] 阈值 {r['threshold']:<12} 示例情景: "
              f"{r['typical_scenario']} (P={r['p_severe_pct']}%)  → {r['suggested_action']}")

    print("\n所有决策表已输出到 output/tables/，热力图为 fig12_motorway_heatmap.png")


if __name__ == "__main__":
    main()
