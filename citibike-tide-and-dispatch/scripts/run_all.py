"""一键复现脚本：从原始数据下载到最终结果的全流程。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STEPS = {
    "download": [
        "src/download_data.py",
        "--year",
        "2019",
        "--months",
        "05",
        "06",
        "07",
        "08",
    ],
    "clean": ["src/clean.py"],
    "agg": ["scripts/build_agg_tables.py"],
    "weather": ["src/weather_download.py"],
    "hourly": ["scripts/fig01_hourly_tide.py"],
    "eda": ["scripts/phase3_eda.py"],
    "tide": ["scripts/phase3_tide.py"],
    "phase4": ["scripts/phase4_weather.py"],
    "phase5": ["scripts/phase5_forecast.py"],
    "phase6": ["scripts/phase6_dispatch.py"],
}
DEFAULT_ORDER = [
    "download",
    "clean",
    "agg",
    "weather",
    "hourly",
    "eda",
    "tide",
    "phase4",
    "phase5",
    "phase6",
]


def run_step(name: str) -> None:
    cmd = [PY, *STEPS[name]]
    print(f"\n===== 步骤 {name}: {' '.join(cmd)} =====")
    subprocess.run(cmd, cwd=ROOT, check=True, env={**os.environ, "PYTHONUTF8": "1"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--steps",
        nargs="+",
        default=DEFAULT_ORDER,
        help=f"要执行的步骤（按顺序），可选 {list(STEPS)}",
    )
    args = parser.parse_args()
    for name in args.steps:
        if name not in STEPS:
            raise SystemExit(f"未知步骤: {name}，可选 {list(STEPS)}")
        run_step(name)
    print("\n全部步骤完成，结果见 output/figures/ 与 output/results/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
