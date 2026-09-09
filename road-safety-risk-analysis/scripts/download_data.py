# -*- coding: utf-8 -*-
"""数据下载脚本"""

import argparse
import sys
import time
import urllib.request
from pathlib import Path

BASE_URL = "https://data.dft.gov.uk/road-accidents-safety-data"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# DfT 不同年份的文件命名有差异：
# - 2017-2019 等早期年份: dftRoadSafetyData_Accidents_YYYY.csv
# - 2020 起的新命名:       dft-road-casualty-statistics-collision-YYYY.csv
# 这里给出映射，实际以服务器上存在的文件为准。
NAME_TEMPLATES = [
    "dft-road-casualty-statistics-collision-{year}.csv",  # 新版
    "dftRoadSafetyData_Accidents_{year}.csv",  # 旧版
]


def file_url_exists(url: str, timeout: int = 20) -> bool:
    """探测文件是否存在（服务器不允许 HEAD，用 Range=0 的 GET 试探）。"""
    req = urllib.request.Request(url, method="GET", headers={"Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 206)
    except Exception:
        return False


def download(url: str, dest: Path) -> None:
    """下载文件到 dest，打印进度（按已下载字节数）。"""
    print(f"  下载中: {url}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (data-collection script)"}
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        total = 0
        while True:
            chunk = resp.read(1 << 20)  # 1 MB
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
            if total % (5 << 20) < (1 << 20):  # 每 5MB 打一次进度
                print(f"    已下载 {total/1e6:.1f} MB ...")
    print(f"  完成: {dest.name} ({total/1e6:.1f} MB, {time.time()-t0:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="下载英国 DfT 道路交通事故数据")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2021, 2022, 2023, 2024],
        help="要下载的年份，例如 2017 2018 2019",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for year in sorted(args.years):
        dest = RAW_DIR / f"collisions_{year}.csv"
        if dest.exists() and dest.stat().st_size > 1_000_000:
            print(f"[跳过] {dest.name} 已存在 ({dest.stat().st_size/1e6:.1f} MB)")
            continue
        found = False
        for template in NAME_TEMPLATES:
            url = f"{BASE_URL}/{template.format(year=year)}"
            if file_url_exists(url):
                download(url, dest)
                found = True
                break
        if not found:
            print(f"[警告] {year} 年数据未找到，请检查文件名规则。", file=sys.stderr)


if __name__ == "__main__":
    main()
