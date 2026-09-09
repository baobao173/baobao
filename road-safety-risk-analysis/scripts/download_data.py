# -*- coding: utf-8 -*-
"""
数据下载脚本
============
从英国交通部 (Department for Transport, DfT) 官方开放数据平台
下载 道路交通事故主表（collision / accident 表，STATS19 口径）。

数据来源与许可:
- 数据集主页: https://www.data.gov.uk/dataset/cb7ae6f0-4be6-4935-9277-47e5ce24a11f/road-accidents-safety-data
- 文件托管:   https://data.dft.gov.uk/road-accidents-safety-data/
- 许可:       UK Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
  允许自由使用、复制与分发，注明来源即可。

该表记录了警察报告的在公共道路上发生的、涉及人身伤亡的碰撞事故
(accidents involving personal injury, reported to the police)，
一条记录 = 一起事故（而非一起伤亡）。

用法:
    python download_data.py --years 2017 2018 2019 2020 2021 2022
"""

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
    "dftRoadSafetyData_Accidents_{year}.csv",              # 旧版
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
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (data-collection script)"})
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
    parser.add_argument("--years", nargs="+", type=int, default=list(range(2017, 2023)),
                        help="要下载的年份，例如 2017 2018 2019")
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
