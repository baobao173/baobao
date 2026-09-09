# -*- coding: utf-8 -*-
"""
03_inference.py — 统计推断：卡方独立性检验 与 Cramér's V 效应量
================================================================
研究问题 2（统计检验部分）：
  事故严重程度（KSI 与否）与"光照、天气、路面、道路类型、城乡、
  时段、是否高速、是否周末"这些因素是否独立？

方法（本科统计学可完整复述）：
  1) 卡方(χ²)独立性检验：H0 = 两变量独立；
     在 37.8 万的大样本下，几乎任何微弱关联都会得到 p < 0.001，
     因此 p 值本身意义有限——必须同时报告效应量。
  2) Cramér's V：V = sqrt( χ² / ( n · (min(r,c)-1) ) )，
     取值 [0,1]，用于衡量关联强度（约定：0.10 小 / 0.30 中 / 0.50 大）。
  3) 两比例 z 检验：例如"夜间无照明"与"白天"的 KSI 率差异是否显著
     （正态近似：z = (p1-p2) / sqrt( p̄(1-p̄)(1/n1 + 1/n2) )）。

输出:
  output/tables/inference_results.csv   各变量的 χ² / p / Cramér's V
  （控制台打印关键解读）
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data" / "processed" / "accidents_clean.csv.gz"
TBL_DIR = PROJECT_ROOT / "output" / "tables"
TBL_DIR.mkdir(parents=True, exist_ok=True)

# 参与独立性检验的分类变量（均为可解释的业务维度）
TEST_COLS = ["light", "weather", "surface", "road_type",
             "area", "period", "is_motorway", "is_weekend"]


def fmt_p(p: float) -> str:
    """p 值格式化：小于 0.001 显示为 <0.001，否则保留 4 位小数。"""
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def cramers_v(chi2: float, n: int, r: int, c: int) -> float:
    """Cramér's V = sqrt(χ² / (n·(min(r,c)-1)))。r、c 为列联表行列数。"""
    return float(np.sqrt(chi2 / (n * (min(r, c) - 1))))


def chi2_test(df: pd.DataFrame, col: str) -> dict:
    """对 col 与 is_severe 做卡方独立性检验，返回各项统计量。"""
    ct = pd.crosstab(df[col], df["is_severe"])
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    return {
        "variable": col,
        "chi2": chi2,
        "p_value": p,
        "dof": dof,
        "cramers_v": cramers_v(chi2, len(df), *ct.shape),
    }


def two_prop_ztest(y1: int, n1: int, y2: int, n2: int) -> dict:
    """两比例之差的正态近似 z 检验（双侧）。返回 z、p、率差。"""
    p1, p2 = y1 / n1, y2 / n2
    p_bar = (y1 + y2) / (n1 + n2)
    se = np.sqrt(p_bar * (1 - p_bar) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se
    p = 2 * (1 - stats.norm.cdf(abs(z)))  # 双侧 p 值
    return {"rate1": p1, "rate2": p2, "diff": p1 - p2, "z": z, "p_value": p}


def main():
    df = pd.read_csv(DATA, compression="gzip", low_memory=False)
    print(f"样本量 n = {len(df):,}\n")

    # ---------- 1) 卡方独立性检验（所有分类变量） ----------
    results = [chi2_test(df, col) for col in TEST_COLS]
    res = pd.DataFrame(results).sort_values("cramers_v", ascending=False)

    print("== 卡方独立性检验：严重程度 vs 各因素 ==")
    print("（大样本下 p 几乎都 < 0.001，务必以 Cramér's V 效应量为准）")
    for _, row in res.iterrows():
        print(f"  {row['variable']:<12} χ²={row['chi2']:>12,.0f}  "
              f"p={fmt_p(row['p_value'])}  "
              f"Cramér's V={row['cramers_v']:.4f}")

    # ---------- 2) 业务上最关心的对比：夜间无照明 vs 白天 ----------
    print("\n== 两比例 z 检验：夜间无/弱照明 vs 白天 的 KSI 率 ==")
    night = df[df["light"] == "夜间-无/弱照明"]
    day = df[df["light"] == "白天"]
    zr = two_prop_ztest(int(night["is_severe"].sum()), len(night),
                        int(day["is_severe"].sum()), len(day))
    print(f"  夜间无/弱照明: KSI率={zr['rate1']*100:.2f}% (n={len(night):,})")
    print(f"  白天:          KSI率={zr['rate2']*100:.2f}% (n={len(day):,})")
    print(f"  率差={zr['diff']*100:.2f} 个百分点, z={zr['z']:.1f}, "
          f"p={fmt_p(zr['p_value'])}")

    # ---------- 3) 保存结果表 ----------
    res["p_value"] = res["p_value"].map(fmt_p)
    res["chi2"] = res["chi2"].round(1)
    res["cramers_v"] = res["cramers_v"].round(4)
    out = TBL_DIR / "inference_results.csv"
    res.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n结果表已输出: {out}")

    # ---------- 4) 解读提示 ----------
    top = res.iloc[0]
    print("\n== 解读 ==")
    print(f"关联最强的是「{top['variable']}」(Cramér's V = {top['cramers_v']})；")
    print("全部 p < 0.001 仅说明'不独立'，效应量才回答'关联多强'。")


if __name__ == "__main__":
    main()
