"""一次性聚合：把 856 万行主表压缩成若干小表，供各阶段分析快速读取。

为什么需要这一步？
------------------
主表 data/processed/trips_clean.csv.gz（约 350 MB，856 万行）每次读取要
1 分钟左右。后续 EDA / 潮汐 / 预测 / 报告都要反复聚合，与其重复读大文件，
不如一次性生成"分析专用小表"：

  data/processed/agg/
  ├── hourly_demand.csv   每小时骑行量/用户结构/平均时长（日期×小时，约 3 千行）
  ├── daily_demand.csv    每日聚合（约 123 行）
  ├── station_flow.csv    每站进出量与早晚高峰净流量（潮汐量化基础）
  └── od_top20.csv        最热门的 20 条起终点线路

用法：
    python scripts/build_agg_tables.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CLEAN_CSV = ROOT / "data/processed/trips_clean.csv.gz"
OUT_DIR = ROOT / "data/processed/agg"

# 本次聚合实际用到的列（减少内存与读取时间）
USE_COLS = [
    "duration_sec", "start_time",
    "start_station_id", "start_station_name", "start_lat", "start_lng",
    "end_station_id", "end_station_name", "end_lat", "end_lng",
    "user_type", "hour", "weekday", "is_weekend",
]

MORNING_HOURS = [7, 8, 9]    # 早高峰 07:00–09:59
EVENING_HOURS = [17, 18, 19]  # 晚高峰 17:00–19:59


def _flow_table(df: pd.DataFrame, key: str, name: str, cond: pd.Series) -> pd.DataFrame:
    """按 key 聚合满足条件 cond 的行程数，输出列统一为 (station_id, name)。"""
    return (df[cond].groupby(key).size().rename(name)
            .reset_index().rename(columns={key: "station_id"}))


def main() -> None:
    print("读取主表 ...")
    df = pd.read_csv(CLEAN_CSV, usecols=USE_COLS, parse_dates=["start_time"])
    df["date"] = df["start_time"].dt.date
    print(f"共 {len(df):,} 行")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- 1. 小时级需求表 ----------
    hourly = df.groupby(["date", "hour", "weekday", "is_weekend"], observed=True).agg(
        rides=("duration_sec", "size"),
        rides_sub=("user_type", lambda s: int(s.eq("Subscriber").sum())),
        rides_cus=("user_type", lambda s: int(s.eq("Customer").sum())),
        avg_dur_sec=("duration_sec", "mean"),
    ).reset_index()
    hourly.to_csv(OUT_DIR / "hourly_demand.csv", index=False)
    print(f"hourly_demand.csv: {len(hourly):,} 行")

    # ---------- 2. 日级需求表 ----------
    daily = df.groupby(["date", "weekday", "is_weekend"], observed=True).agg(
        rides=("duration_sec", "size"),
        rides_sub=("user_type", lambda s: int(s.eq("Subscriber").sum())),
        rides_cus=("user_type", lambda s: int(s.eq("Customer").sum())),
        avg_dur_sec=("duration_sec", "mean"),
    ).reset_index()
    daily.to_csv(OUT_DIR / "daily_demand.csv", index=False)
    print(f"daily_demand.csv: {len(daily):,} 行")

    # ---------- 3. 站点进出流量表（含早晚高峰净流出 = 潮汐方向） ----------
    morning = df["hour"].isin(MORNING_HOURS)
    evening = df["hour"].isin(EVENING_HOURS)

    out_all = (df.groupby(["start_station_id", "start_station_name",
                           "start_lat", "start_lng"]).size().rename("rides_out")
               .reset_index().rename(columns={"start_station_id": "station_id",
                                              "start_station_name": "station_name",
                                              "start_lat": "lat", "start_lng": "lng"}))
    in_all = (df.groupby(["end_station_id", "end_station_name",
                          "end_lat", "end_lng"]).size().rename("rides_in")
              .reset_index().rename(columns={"end_station_id": "station_id",
                                             "end_station_name": "station_name",
                                             "end_lat": "lat", "end_lng": "lng"}))

    # 全站并集（有的站只被借出或只被归还，需 outer join 并补全缺失侧）
    station = out_all.merge(in_all, on="station_id", how="outer", suffixes=("", "_in"))
    for c in ["station_name", "lat", "lng"]:
        station[c] = station[c].fillna(station[f"{c}_in"])
        station = station.drop(columns=[f"{c}_in"])
    station[["rides_out", "rides_in"]] = station[["rides_out", "rides_in"]].fillna(0)

    # 早晚高峰的分方向流量
    m_out = _flow_table(df, "start_station_id", "morning_out", morning)
    m_in = _flow_table(df, "end_station_id", "morning_in", morning)
    e_out = _flow_table(df, "start_station_id", "evening_out", evening)
    e_in = _flow_table(df, "end_station_id", "evening_in", evening)
    for sub in (m_out, m_in, e_out, e_in):
        station = station.merge(sub, on="station_id", how="left")
    station = station.fillna(0)

    station["net_morning"] = station["morning_out"] - station["morning_in"]  # >0 早高峰净借出
    station["net_evening"] = station["evening_out"] - station["evening_in"]  # <0 晚高峰净归还
    station = station.sort_values("rides_out", ascending=False).reset_index(drop=True)

    # 业务标签：早高峰车从哪来（供给/居住区）、往哪去（需求/办公区）
    def tide_label(net: float) -> str:
        if net >= 20:
            return "早高峰净借出(居住区)"
        if net <= -20:
            return "早高峰净归还(办公区)"
        return "均衡"

    station["tide_type"] = station["net_morning"].map(tide_label)
    station.to_csv(OUT_DIR / "station_flow.csv", index=False)
    print(f"station_flow.csv: {len(station):,} 站")
    print(station["tide_type"].value_counts().to_string())

    # ---------- 4. 热门线路 Top20 ----------
    od = (df.groupby(["start_station_name", "end_station_name"]).size()
          .rename("rides").reset_index().sort_values("rides", ascending=False))
    od.head(20).to_csv(OUT_DIR / "od_top20.csv", index=False)
    print("od_top20.csv 已保存")

    print("\n聚合完成 ✅")


if __name__ == "__main__":
    main()
