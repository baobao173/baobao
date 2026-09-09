# -*- coding: utf-8 -*-
"""
run_all.py — 一键复现完整分析流水线
====================================
依次执行 01(清洗) → 02(EDA) → 03(推断) → 04(模型) → 05(决策)。

用法:
    python scripts/run_all.py
"""

import subprocess
import sys
from pathlib import Path

# 统一 UTF-8 输出，避免 Windows GBK 终端下中文/emoji 报错
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = [
    "01_clean.py",       # 清洗与特征工程 -> data/processed/accidents_clean.csv.gz
    "02_eda.py",         # 描述统计与 8 张图
    "03_inference.py",   # 卡方检验 + Cramér's V
    "04_model.py",       # 逻辑回归 OR/CI/ROC
    "05_decision.py",    # 风险清单与红黄绿规则
]


def main() -> None:
    for name in SCRIPTS:
        script = PROJECT_ROOT / "scripts" / name
        print(f"\n===== 运行 {name} =====")
        subprocess.run([sys.executable, str(script)], check=True)
    print("\n[完成] 全部 5 步跑通：图表在 output/figures/，表格在 output/tables/，"
          "清洗数据在 data/processed/accidents_clean.csv.gz")


if __name__ == "__main__":
    main()
