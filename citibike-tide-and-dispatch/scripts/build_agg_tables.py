"""分块聚合骑行记录；借出按 start_time，归还按 end_time。"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/processed/agg"


def event_counts(df, kind):
    prefix = "start" if kind == "out" else "end"
    time = df[prefix + "_time"]
    part = pd.DataFrame(
        {
            "date": time.dt.normalize(),
            "hour": time.dt.hour,
            "station_id": df[prefix + "_station_id"],
        }
    )
    return part.groupby(["date", "hour", "station_id"]).size().rename(kind)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    hourly_parts = []
    events = []
    meta = []
    od = []
    cols = [
        "start_time",
        "end_time",
        "duration_sec",
        "user_type",
        "start_station_id",
        "end_station_id",
        "start_station_name",
        "end_station_name",
        "start_lat",
        "start_lng",
        "end_lat",
        "end_lng",
    ]
    for df in pd.read_csv(
        ROOT / "data/processed/trips_clean.csv.gz",
        usecols=cols,
        parse_dates=["start_time", "end_time"],
        chunksize=300000,
    ):
        df["timestamp"] = df.start_time.dt.floor("h")
        df["subscriber"] = df.user_type.eq("Subscriber").astype(int)
        df["customer"] = df.user_type.eq("Customer").astype(int)
        hourly_parts.append(
            df.groupby("timestamp").agg(
                rides=("duration_sec", "size"),
                rides_sub=("subscriber", "sum"),
                rides_cus=("customer", "sum"),
                duration_sum=("duration_sec", "sum"),
            )
        )
        events.extend(
            [event_counts(df, "out").to_frame(), event_counts(df, "in").to_frame()]
        )
        for prefix in ["start", "end"]:
            m = df[
                [
                    prefix + "_station_id",
                    prefix + "_station_name",
                    prefix + "_lat",
                    prefix + "_lng",
                ]
            ].drop_duplicates(prefix + "_station_id")
            m.columns = ["station_id", "station_name", "lat", "lng"]
            meta.append(m)
        od.append(
            df.groupby(["start_station_name", "end_station_name"])
            .size()
            .rename("rides")
        )
    hourly = pd.concat(hourly_parts).groupby(level=0).sum()
    calendar = pd.date_range("2019-05-01", "2019-08-31 23:00", freq="h")
    hourly = hourly.reindex(calendar, fill_value=0)
    hourly["avg_dur_sec"] = hourly.duration_sum / hourly.rides.replace(0, np.nan)
    hourly["date"] = hourly.index.normalize()
    hourly["hour"] = hourly.index.hour
    hourly["weekday"] = hourly.index.dayofweek
    hourly["is_weekend"] = hourly.weekday >= 5
    hourly.drop(columns="duration_sum").to_csv(OUT / "hourly_demand.csv", index=False)
    daily = hourly.groupby("date")[
        ["rides", "rides_sub", "rides_cus", "duration_sum"]
    ].sum()
    daily["avg_dur_sec"] = daily.duration_sum / daily.rides.replace(0, np.nan)
    daily["weekday"] = daily.index.dayofweek
    daily["is_weekend"] = daily.weekday >= 5
    daily.drop(columns="duration_sum").to_csv(OUT / "daily_demand.csv")
    flow = pd.concat(events).fillna(0).groupby(level=[0, 1, 2]).sum().reset_index()
    flow = flow[flow.date.between("2019-05-01", "2019-08-31")].copy()
    flow["is_weekend"] = flow.date.dt.dayofweek >= 5
    # 唯一站点编号对应一行属性，避免名称/坐标变更导致多对多连接。
    station = (
        pd.concat(meta)
        .drop_duplicates("station_id", keep="last")
        .set_index("station_id")
    )
    totals = (
        flow.groupby("station_id")[["out", "in"]]
        .sum()
        .rename(columns={"out": "rides_out", "in": "rides_in"})
    )
    station = station.join(totals).fillna(0)
    wd = flow[~flow.is_weekend]
    for period, hours in [("morning", [7, 8, 9]), ("evening", [17, 18, 19])]:
        p = wd[wd.hour.isin(hours)].groupby("station_id")[["out", "in"]].sum()
        p = p.rename(columns={"out": period + "_out", "in": period + "_in"})
        station = station.join(p).fillna(0)
        station["net_" + period] = station[period + "_out"] - station[period + "_in"]
    station["tide_type"] = np.select(
        [station.net_morning > 0, station.net_morning < 0],
        ["早高峰净借出", "早高峰净归还"],
        default="均衡",
    )
    station.reset_index().to_csv(OUT / "station_flow.csv", index=False)
    morning = (
        flow[flow.hour.isin([7, 8, 9])]
        .groupby(["date", "station_id"])[["out", "in"]]
        .sum()
    )
    morning["positive_net"] = (morning["out"] - morning["in"]).clip(lower=0)
    migration = (
        morning.groupby("date").positive_net.sum().rename("migration").to_frame()
    )
    migration["weekday"] = migration.index.dayofweek
    migration["is_weekend"] = migration.weekday >= 5
    migration.to_csv(OUT / "daily_migration.csv")
    curve = []
    for kind in ["早高峰净借出", "早高峰净归还"]:
        ids = station.index[station.tide_type == kind]
        p = (
            wd[wd.station_id.isin(ids)]
            .groupby("hour")[["out", "in"]]
            .sum()
            .reindex(range(24), fill_value=0)
        )
        p["net"] = (p["out"] - p["in"]) / sum(
            calendar.normalize().unique().dayofweek < 5
        )
        p["group"] = kind
        curve.append(p.reset_index())
    pd.concat(curve).to_csv(OUT / "hourly_net_groups.csv", index=False)
    pd.concat(od).groupby(level=[0, 1]).sum().nlargest(20).to_csv(OUT / "od_top20.csv")
    assert station.index.is_unique
    assert int(hourly.rides.sum()) == int(flow["out"].sum())
    print(f"聚合完成：{len(hourly)} 小时，{len(station)} 个唯一站点")


if __name__ == "__main__":
    main()
