"""获取并解析纽约 2019 年 5–8 月小时级天气数据（Open-Meteo 历史天气 API）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import requests

API = "https://archive-api.open-meteo.com/v1/archive"
# 纽约中央公园附近（Citi Bike 服务区中心地带）
LAT, LNG = 40.7794, -73.9692

# WMO 天气码 -> 简化天气分类（用于分析与绘图）
WMO_MAP = {
    0: "晴",
    1: "多云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾",
    51: "小雨",
    53: "小雨",
    55: "小雨",
    56: "小雨",
    57: "小雨",
    61: "雨",
    63: "雨",
    65: "大雨",
    66: "雨",
    67: "雨",
    71: "雪",
    73: "雪",
    75: "雪",
    77: "雪",
    80: "阵雨",
    81: "阵雨",
    82: "大雨",
    85: "雪",
    86: "雪",
    95: "雷雨",
    96: "雷雨",
    99: "雷雨",
}


def fetch_weather(start: str, end: str) -> pd.DataFrame:
    params = {
        "latitude": LAT,
        "longitude": LNG,
        "start_date": start,
        "end_date": end,
        "hourly": "temperature_2m,precipitation,weather_code,wind_speed_10m,relative_humidity_2m",
        "timezone": "America/New_York",
        "models": "era5",
    }
    resp = requests.get(API, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    h = data["hourly"]
    df = pd.DataFrame(
        {
            "datetime_local": pd.to_datetime(h["time"]),
            "temp_c": h["temperature_2m"],
            "precip_mm": h["precipitation"],
            "wind_kmh": h["wind_speed_10m"],
            "humidity_pct": h["relative_humidity_2m"],
            "weather_code": h["weather_code"],
        }
    )
    df["condition"] = df["weather_code"].map(lambda c: WMO_MAP.get(int(c), "其他"))
    df["date"] = df["datetime_local"].dt.date
    df["hour"] = df["datetime_local"].dt.hour
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2019-05-01")
    parser.add_argument("--end", default="2019-08-31")
    parser.add_argument(
        "--out", type=Path, default=Path("data/raw/weather_2019_0508.csv")
    )
    args = parser.parse_args()

    df = fetch_weather(args.start, args.end)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    print(f"已保存: {args.out}（{len(df)} 小时，{df['date'].nunique()} 天）")
    print("\n===== 天气摘要 =====")
    print(df[["temp_c", "precip_mm", "wind_kmh"]].describe().round(1).to_string())
    print("\n===== 天气分类计数 =====")
    print(df["condition"].value_counts().to_string())
    print(f"\n日期范围: {df['datetime_local'].min()} ~ {df['datetime_local'].max()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
