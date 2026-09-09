"""清洗脚本：合并原始月度 CSV -> 统一列名 -> 业务规则清洗 -> 派生时间字段。"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("clean")

# 官方旧版 15 列 -> 本项目统一命名（全小写、空格转下划线）
COLUMN_MAP = {
    "tripduration": "duration_sec",
    "starttime": "start_time",
    "stoptime": "end_time",
    "start station id": "start_station_id",
    "start station name": "start_station_name",
    "start station latitude": "start_lat",
    "start station longitude": "start_lng",
    "end station id": "end_station_id",
    "end station name": "end_station_name",
    "end station latitude": "end_lat",
    "end station longitude": "end_lng",
    "bikeid": "bike_id",
    "usertype": "user_type",
    "birth year": "birth_year",
    "gender": "gender",
}

# 业务清洗规则（数值单位：秒）
MIN_DURATION_SEC = 60  # 官方已剔除 <60s，这里保留同样口径便于叙述
MAX_DURATION_SEC = 4 * 3600  # 超过 4 小时视为异常（异常归还/测试行程）

STATION_ID_COLS = ["start_station_id", "end_station_id"]
STATION_GEO_COLS = ["start_lat", "start_lng", "end_lat", "end_lng"]


def load_raw_files(raw_dir: Path) -> pd.DataFrame:
    """读取 raw 目录下所有年份月度 CSV 并合并。"""
    # 匹配所有月度 CSV（超百万行的月份会被官方拆成 _1/_2/_3 多个文件）
    files = sorted(
        p
        for p in raw_dir.glob("2019*-citibike-tripdata*.csv")
        if p.name[4:6] in {"05", "06", "07", "08"}
    )
    if not files:
        raise FileNotFoundError(
            f"{raw_dir} 下没有找到原始 CSV，请先运行 src/download_data.py"
        )
    frames = []
    for f in files:
        df = pd.read_csv(f, parse_dates=["starttime", "stoptime"], low_memory=False)
        frames.append(df)
        log.info("读取 %s：%d 行", f.name, len(df))
    raw = pd.concat(frames, ignore_index=True)
    log.info("合并后共 %d 行，%d 列", len(raw), raw.shape[1])
    return raw


def clean_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """按业务规则清洗，返回 (干净数据, 清洗日志)。"""
    n0 = len(df)
    log_book: dict[str, int] = {}

    # 规则 1：时间顺序合法（结束须晚于出发）
    mask_time = df["end_time"] > df["start_time"]
    log_book["结束时间不晚于出发时间"] = int((~mask_time).sum())
    df = df[mask_time]

    # 规则 2：时长在合理区间（60 秒 ~ 4 小时）
    mask_dur = df["duration_sec"].between(MIN_DURATION_SEC, MAX_DURATION_SEC)
    log_book["时长超出 60s~4h 区间"] = int((~mask_dur).sum())
    df = df[mask_dur]

    # 规则 3：关键站点字段完整（站点编号与经纬度）
    mask_station = df[STATION_ID_COLS].notna().all(axis=1) & df[
        STATION_GEO_COLS
    ].notna().all(axis=1)
    log_book["起终点站点信息缺失"] = int((~mask_station).sum())
    df = df[mask_station]

    # 规则 4：经纬度落在纽约市合理范围（防脏坐标）
    in_range = (
        df["start_lat"].between(40.5, 41.0)
        & df["end_lat"].between(40.5, 41.0)
        & df["start_lng"].between(-74.3, -73.7)
        & df["end_lng"].between(-74.3, -73.7)
    )
    log_book["经纬度超出纽约范围"] = int((~in_range).sum())
    df = df[in_range]

    kept = len(df)
    log.info("清洗完成：保留 %d / %d 行（%.2f%%）", kept, n0, kept / n0 * 100)
    return df.reset_index(drop=True), log_book


def derive_features(df: pd.DataFrame) -> pd.DataFrame:
    """派生时间特征：date / hour / weekday / is_weekend / period。"""
    t = df["start_time"].dt
    df["date"] = df["start_time"].dt.date
    df["hour"] = t.hour
    df["weekday"] = t.dayofweek  # 周一=0 ... 周日=6
    df["is_weekend"] = df["weekday"] >= 5
    df["period"] = pd.cut(
        df["hour"],
        bins=[-1, 6, 9, 16, 19, 23],
        labels=["夜间", "早高峰", "日间平峰", "晚高峰", "夜间2"],
        include_lowest=False,
    )
    # 合并两个"夜间"标签（pd.cut 无法对首尾区间取同名，这里做一次规整）
    df["period"] = df["period"].astype(str).replace({"夜间2": "夜间"})
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--out", type=Path, default=Path("data/processed/trips_clean.csv.gz")
    )
    parser.add_argument(
        "--sample-lines",
        type=int,
        default=5,
        help="打印清洗结果的样例行数，便于快速核对",
    )
    args = parser.parse_args()

    import gzip

    files = sorted(
        p
        for p in args.raw_dir.glob("2019*-citibike-tripdata*.csv")
        if p.name[4:6] in {"05", "06", "07", "08"}
    )
    if not files:
        raise FileNotFoundError("请先下载 2019 年 5–8 月的 CSV")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    n_raw = n_clean = 0
    log_book = {}
    with gzip.open(args.out, "wt", encoding="utf-8", newline="") as out:
        for path in files:
            for raw in pd.read_csv(path, chunksize=250000, low_memory=False):
                raw = raw.rename(columns=COLUMN_MAP)
                for col in ["start_time", "end_time"]:
                    raw[col] = pd.to_datetime(raw[col], errors="coerce", format="mixed")
                cleaned, counts = clean_frame(raw)
                cleaned = derive_features(cleaned)
                cleaned.to_csv(out, index=False, header=n_raw == 0)
                n_raw += len(raw)
                n_clean += len(cleaned)
                for rule, count in counts.items():
                    log_book[rule] = log_book.get(rule, 0) + count
            print(f"{path.name}: 累计保留 {n_clean:,} / {n_raw:,}", flush=True)
    audit = Path(__file__).resolve().parent.parent / "output/results/cleaning.json"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        json.dumps(
            {"raw_rows": n_raw, "clean_rows": n_clean, "removed_by_rule": log_book},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
