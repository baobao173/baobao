# -*- coding: utf-8 -*-
"""01_clean.py — 数据清洗与特征工程"""

import re
import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

YEARS = [2021, 2022, 2023, 2024]


# ------------------------- 1. 读取与合并 -------------------------
def load_raw(years):
    """读取各年 collision 表并纵向合并。"""
    frames = []
    for y in years:
        path = RAW_DIR / f"collisions_{y}.csv"
        df = pd.read_csv(path, low_memory=False)
        # collision_index 是字符串型事故编号，但 pandas 可能推断为数值，统一转字符串
        df["collision_index"] = df["collision_index"].astype(str)
        print(f"  {y}: {len(df):,} 起事故")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# ------------------------- 2. 严重程度与基础变量 -------------------------
SEVERITY_LABEL = {1: "Fatal", 2: "Serious", 3: "Slight"}


def clean_basics(df: pd.DataFrame) -> pd.DataFrame:
    """解析日期时间、构造严重性二分类标签（KSI = Fatal 或 Serious）。"""
    df = df.copy()
    df["severity"] = df["collision_severity"].map(SEVERITY_LABEL)
    df["is_severe"] = (df["collision_severity"] <= 2).astype(int)  # 1 = 死亡或重伤

    # 日期：格式 DD/MM/YYYY
    df["date_dt"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    df["year"] = df["date_dt"].dt.year
    df["month"] = df["date_dt"].dt.month

    # 时刻：格式 HH:MM
    def to_hour(t):
        m = re.match(r"^(\d{1,2}):", str(t))
        return int(m.group(1)) if m else np.nan

    df["hour"] = df["time"].map(to_hour)
    df["day_of_week_num"] = df["day_of_week"]  # 1=周日、2=周一 ... 7=周六
    df["is_weekend"] = (df["day_of_week_num"].isin([1, 7])).astype(int)
    return df


def period_of(hour):
    """把小时映射成业务时段（可解释分组，模型里作哑变量）。"""
    if pd.isna(hour):
        return "unknown"
    if hour <= 5:
        return "深夜 0-5"
    if hour <= 9:
        return "早高峰 6-9"
    if hour <= 15:
        return "白天 10-15"
    if hour <= 19:
        return "晚高峰 16-19"
    return "夜间 20-23"


# ------------------------- 3. 官方编码 → 业务标签 -------------------------
def label_categorical(df: pd.DataFrame) -> pd.DataFrame:
    """把 STATS19 数字编码翻译成可读分组，并合并小样本类别。"""
    df = df.copy()

    # 光照：突出"夜间有无照明"——这是预警系统最有意义的维度
    def light(x):
        return {
            1: "白天",
            4: "夜间-有照明",
            5: "夜间-无/弱照明",
            6: "夜间-无/弱照明",
            7: "不明",
        }.get(x, "不明")

    # 天气：把"大风"并入同种降水情形，便于解释
    def weather(x):
        return {
            1: "晴",
            2: "雨",
            3: "雪",
            4: "晴",
            5: "雨",
            6: "雪",
            7: "雾",
            8: "其他",
            9: "不明",
        }.get(x, "不明")

    # 路面
    def surface(x):
        return {
            1: "干燥",
            2: "湿滑",
            3: "积雪",
            4: "结冰",
            5: "积水",
            6: "油污等",
            9: "不明",
        }.get(x, "不明")

    # 道路类型
    def road_type(x):
        return {
            1: "环岛",
            2: "单行路",
            3: "双向分隔路",
            4: "其他",
            6: "单幅路",
            7: "匝道",
            9: "不明",
        }.get(x, "其他")

    df["light"] = df["light_conditions"].map(light)
    df["weather"] = df["weather_conditions"].map(weather)
    df["surface"] = df["road_surface_conditions"].map(surface)
    df["road_type"] = df["road_type"].map(road_type)
    df["period"] = df["hour"].map(period_of)

    # 城乡：3=未划分，样本极少，直接剔除
    df = df[df["urban_or_rural_area"].isin([1, 2])].copy()
    df["area"] = df["urban_or_rural_area"].map({1: "城市", 2: "乡村"})

    # 高速公路标志：first_road_class == 1 (Motorway)
    df["is_motorway"] = (df["first_road_class"] == 1).astype(int)
    return df


# ------------------------- 4. 缺失值处理 -------------------------
def drop_insufficient(df: pd.DataFrame) -> pd.DataFrame:
    """剔除关键变量缺失/未知的行，保留分析可用样本。"""
    before = len(df)
    df = df[
        df["severity"].notna()
        & df["date_dt"].notna()
        & df["hour"].between(0, 23)
        & df["light"].isin(["白天", "夜间-有照明", "夜间-无/弱照明"])
        & df["weather"].isin(["晴", "雨", "雪", "雾"])  # 天气不明/其他 剔除
        & df["surface"].isin(["干燥", "湿滑", "积雪", "结冰", "积水"])
        & df["road_type"].isin(["单幅路", "双向分隔路", "环岛", "匝道", "单行路"])
        & df["speed_limit"].isin([20, 30, 40, 50, 60, 70])
    ].copy()
    print(
        f"  缺失/不明样本剔除: {before - len(df):,} 条 ({100*(before-len(df))/before:.1f}%)"
    )
    return df


# ------------------------- 5. 主流程 -------------------------
def main():
    print("== 1) 读取原始数据 ==")
    df = load_raw(YEARS)
    n_raw = len(df)
    print(f"合并后总计: {len(df):,} 起事故")

    print("\n== 2) 清洗基础变量 ==")
    df = clean_basics(df)

    print("\n== 3) 编码 -> 业务标签 ==")
    df = label_categorical(df)

    print("\n== 4) 剔除关键变量缺失样本 ==")
    df = drop_insufficient(df)
    print(f"最终分析样本: {len(df):,} 起事故")

    # 保留分析所需列（含经纬度用于空间图）
    cols = [
        "collision_index",
        "date_dt",
        "year",
        "month",
        "hour",
        "day_of_week_num",
        "is_weekend",
        "period",
        "severity",
        "is_severe",
        "light",
        "weather",
        "surface",
        "road_type",
        "is_motorway",
        "area",
        "speed_limit",
        "number_of_vehicles",
        "number_of_casualties",
        "longitude",
        "latitude",
    ]
    df = df[cols]
    for col in ["year", "month", "hour", "speed_limit", "day_of_week_num"]:
        df[col] = df[col].astype(int)
    quality = {
        "raw_rows": n_raw,
        "clean_rows": len(df),
        "removed_rows": n_raw - len(df),
        "sources": [
            {
                "year": y,
                "sha256": hashlib.sha256(
                    (RAW_DIR / f"collisions_{y}.csv").read_bytes()
                ).hexdigest(),
            }
            for y in YEARS
        ],
    }
    audit = PROJECT_ROOT / "output/tables/data_quality.json"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "accidents_clean.csv.gz"
    df.to_csv(out, index=False, compression="gzip")
    print(
        f"\n已输出: {out} ({out.stat().st_size/1e6:.1f} MB, {len(df):,} 行 x {df.shape[1]} 列)"
    )

    # 摘要统计
    print("\n== 总体严重事故率 (KSI) ==")
    print(f"  整体: {df['is_severe'].mean()*100:.2f}%")
    for year in YEARS:
        sub = df[df["year"] == year]
        print(f"  {year}: n={len(sub):,}, KSI率={sub['is_severe'].mean()*100:.2f}%")


if __name__ == "__main__":
    main()
