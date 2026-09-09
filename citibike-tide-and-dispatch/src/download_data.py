"""下载 Citi Bike 月度骑行数据（纽约）。"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("download")

# Citi Bike 的年度 / 月度压缩包命名规律
YEARLY_URL = "https://s3.amazonaws.com/tripdata/{year}-citibike-tripdata.zip"
MONTHLY_URL = "https://s3.amazonaws.com/tripdata/{yyyymm}-citibike-tripdata.zip"


def remote_size(url: str, timeout: int = 30) -> int:
    """用 HEAD 请求拿到远端文件总字节数。"""
    resp = requests.head(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    size = int(resp.headers.get("Content-Length", -1))
    if size < 0:
        raise ValueError(f"无法从响应头获取文件大小: {url}")
    return size


def download_one_chunk(
    url: str, start: int, end: int, dest: Path, retries: int = 6
) -> bool:
    """下载 [start, end] 一个分片到 dest.part{start}。

    返回 True 表示本次成功写满；已存在且大小正确的分片直接跳过（断点续传）。
    分片内部按 1 MB 粒度读取；连接中途断开（国际链路常见）时整片重试。
    """
    part_file = dest.with_name(f"{dest.name}.part{start}")
    expect = end - start + 1
    if part_file.exists() and part_file.stat().st_size == expect:
        return True

    for attempt in range(1, retries + 1):
        try:
            if part_file.exists():
                part_file.unlink()
            headers = {"Range": f"bytes={start}-{end}"}
            with requests.get(
                url, headers=headers, stream=True, timeout=(10, 120)
            ) as resp:
                resp.raise_for_status()
                with open(part_file, "wb") as fh:
                    for buf in resp.iter_content(chunk_size=1024 * 1024):
                        fh.write(buf)
            if part_file.stat().st_size != expect:
                raise IOError(f"分片字节数不符: {part_file.stat().st_size} != {expect}")
            return True
        except (requests.RequestException, IOError) as exc:
            log.warning("分片 %s 第 %d/%d 次失败: %s", start, attempt, retries, exc)
            if attempt == retries:
                raise
            time.sleep(min(2**attempt, 30))
    return False  # 不可达，仅为类型提示


def parallel_download(
    url: str, dest: Path, num_workers: int = 8, chunk_mb: int = 8, retries: int = 6
) -> Path:
    """把整个文件切成 chunk_mb 的分片，用 num_workers 个线程并发下载后拼接。"""
    total = remote_size(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 已完整下载则直接返回（幂等，方便重跑）
    if dest.exists() and dest.stat().st_size == total:
        log.info(
            "目标文件已存在且完整，跳过下载: %s (%.1f MB)", dest.name, total / 1048576
        )
        return dest

    chunk = chunk_mb * 1024 * 1024
    ranges = [
        (start, min(start + chunk - 1, total - 1)) for start in range(0, total, chunk)
    ]
    log.info(
        "开始下载 %s (%.1f MB)，共 %d 个分片，%d 线程",
        dest.name,
        total / 1048576,
        len(ranges),
        num_workers,
    )

    done = 0
    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        futures = {
            pool.submit(download_one_chunk, url, s, e, dest, retries): (s, e)
            for s, e in ranges
        }
        for fut in as_completed(futures):
            fut.result()  # 出错会在这里抛出来
            done += 1
            if done % 10 == 0 or done == len(futures):
                log.info("分片进度 %d/%d", done, len(futures))

    # 按顺序拼接所有分片成完整文件
    log.info("分片全部完成，开始拼接...")
    with open(dest, "wb") as out:
        for start, _ in ranges:
            part = dest.with_name(f"{dest.name}.part{start}")
            with open(part, "rb") as fh:
                out.write(fh.read())
            part.unlink()
    assert dest.stat().st_size == total, "拼接后大小与远端不一致！"
    log.info("下载完成: %s (%.1f MB)", dest.name, dest.stat().st_size / 1048576)
    return dest


def extract_months(zip_path: Path, months: list[str], out_dir: Path) -> list[str]:
    """从年度 zip 中只解压指定月份（如 '05'）的 CSV，返回解压出的文件名列表。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
        year_prefix = zip_path.stem.split("-")[0]
        for month in months:
            # zip 内为目录分层结构，如 2019-citibike-tripdata/4_April/201904-citibike-tripdata_1.csv
            hit = [
                m for m in members if Path(m).name.startswith(f"{year_prefix}{month}-")
            ]
            if not hit:
                log.warning(
                    "压缩包中未找到 %s 月的文件（现有条目示例：%s）", month, members[:3]
                )
                continue
            for member in hit:
                target = out_dir / Path(member).name
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                extracted.append(target.name)
                log.info("已解压: %s", target.name)
    return extracted


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--year", type=int, default=2019, help="数据年份（2024 之前为年度包）"
    )
    parser.add_argument(
        "--months",
        nargs="+",
        default=["05", "06", "07", "08"],
        help="需要解压的月份（两位数字，默认 05 06 07 08）",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("data/raw"), help="原始数据保存目录"
    )
    parser.add_argument("--workers", type=int, default=8, help="并发下载线程数")
    parser.add_argument("--chunk-mb", type=int, default=8, help="每个分片的大小（MB）")
    parser.add_argument(
        "--retries", type=int, default=6, help="单个分片下载失败的重试次数"
    )
    args = parser.parse_args()

    if args.year >= 2024:
        log.error("2024 年起为月度包，本脚本暂只支持 2024 年之前的年度包。")
        return 1

    url = YEARLY_URL.format(year=args.year)
    zip_path = (args.out_dir / f"{args.year}-citibike-tripdata.zip").resolve()
    parallel_download(
        url,
        zip_path,
        num_workers=args.workers,
        chunk_mb=args.chunk_mb,
        retries=args.retries,
    )
    extract_months(zip_path, args.months, args.out_dir.resolve())
    log.info("全部完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
