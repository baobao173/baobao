"""一键复现脚本：从原始数据下载到最终结果的全流程。

用法（在项目根目录，使用项目的 Python 环境）：
    python scripts/run_all.py                                  # 全流程
    python scripts/run_all.py --steps clean phase5             # 只跑指定步骤

步骤顺序与依赖：
    download -> clean -> agg -> weather -> eda -> tide -> phase4 -> phase5 -> phase6

说明：
  * download 会下载约 819MB 官方年度包（多线程断点续传），已下载完整则自动跳过；
  * weather 需要联网调用 Open-Meteo API；
  * 各步骤幂等：重复运行会覆盖对应输出，不会破坏原始数据。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

STEPS = {
    "download": ["src/download_data.py", "--year", "2019", "--months", "05", "06", "07", "08"],
    "clean": ["src/clean.py"],
    "agg": ["scripts/build_agg_tables.py"],
    "weather": ["src/weather_download.py"],
    "eda": ["scripts/phase3_eda.py"],
    "tide": ["scripts/phase3_tide.py"],
    "phase4": ["scripts/phase4_weather.py"],
    "phase5": ["scripts/phase5_forecast.py"],
    "phase6": ["scripts/phase6_dispatch.py"],
}
DEFAULT_ORDER = ["download", "clean", "agg", "weather", "eda", "tide",
                 "phase4", "phase5", "phase6"]


def run_step(name: str) -> None:
    cmd = [PY, *STEPS[name]]
    print(f"\n===== 步骤 {name}: {' '.join(cmd)} =====")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", nargs="+", default=DEFAULT_ORDER,
                        help=f"要执行的步骤（按顺序），可选 {list(STEPS)}")
    args = parser.parse_args()
    for name in args.steps:
        if name not in STEPS:
            raise SystemExit(f"未知步骤: {name}，可选 {list(STEPS)}")
        run_step(name)
    print("\n全部步骤完成 ✅ 结果见 output/figures/ 与 output/results/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
