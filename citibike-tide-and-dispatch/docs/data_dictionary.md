# 数据字典（Data Dictionary）

> 状态：已按 2019 年 5–8 月实际下载数据校准（11 个官方月度 CSV，字段与下表一致）。

## 一、骑行数据（Citi Bike，2019 旧版格式，15 列）

来源：`https://s3.amazonaws.com/tripdata/2019-citibike-tripdata.zip`（内含各月 CSV）

| 原始字段 | 类型 | 含义 | 本项目用途 |
|---|---|---|---|
| `tripduration` | int（秒） | 骑行时长 | 清洗剔除异常；用户行为差异 |
| `starttime` | datetime | 出发时间 | 时间维度：小时/星期/高峰 |
| `stoptime` | datetime | 到达时间 | 校验（须晚于出发） |
| `start station id` | int | 出发站点编号 | 站点级聚合 |
| `start station name` | str | 出发站点名称 | 展示 |
| `start station latitude` | float | 出发站点纬度 | 空间可视化 |
| `start station longitude` | float | 出发站点经度 | 空间可视化 |
| `end station id` | int | 到达站点编号 | 站点级聚合 |
| `end station name` | str | 到达站点名称 | 展示 |
| `end station latitude` | float | 到达站点纬度 | 空间可视化 |
| `end station longitude` | float | 到达站点经度 | 空间可视化 |
| `bikeid` | int | 车辆编号 | 车辆级检查（可选） |
| `usertype` | str | `Subscriber`=年卡 / `Customer`=临时卡 | 通勤 vs 休闲对比 |
| `birth year` | int | 出生年 | 用户画像（可选） |
| `gender` | int | 0=未知 1=男 2=女 | 用户画像（可选） |

官方口径：已剔除员工/测试用车及 <60 秒行程；每月骑行超百万时拆分为多文件（`_1/_2/_3`）。

## 二、派生字段（由 clean.py / features.py 生成）

| 字段 | 定义 | 用途 |
|---|---|---|
| `date` | 出发日期（YYYY-MM-DD） | 按日聚合 |
| `hour` | 出发小时 0–23 | 潮汐曲线 |
| `weekday` | 周一=0 … 周日=6 | 工作日 vs 周末 |
| `is_weekend` | 是否周末 | 分组变量 |
| `is_holiday` | 是否美国节假日（可选） | 控制变量 |
| `period` | 时段标签：夜间 0–7 / 早高峰 7–10 / 日间平峰 10–17 / 晚高峰 17–20 / 夜间 20–24 | 潮汐分析 |

## 三、天气数据（NOAA，待接入）

| 字段 | 类型 | 含义 |
|---|---|---|
| `date` / `hour` | datetime | 观测时刻（对齐骑行数据） |
| `temp` | float | 温度（℃） |
| `feels_like` | float | 体感温度（可选） |
| `humidity` | float | 相对湿度（可选） |
| `wind_speed` | float | 风速 |
| `precip` | float | 降水量 |
| `snow` | float | 降雪量 |
| `condition` | str | 天气状况分类（可选） |

> 注意：NOAA 原始 CSV 单位可能为英制/公制、缺失值常编码为 `-9999`，接入时须统一处理并在本文件记录。

## 四、复现说明

- 原始骑行数据由 `src/download_data.py` 下载（不入 git 库）。
- 天气数据下载方式与脚本在接入阶段补充。

## 五、实测记录（2019 年 5–8 月）

| 月份 | 官方文件数 | 原始行数 |
|---|---|---|
| 2019-05 | 2（`_1/_2`） | 1,924,563 |
| 2019-06 | 3 | 2,125,370 |
| 2019-07 | 3 | 2,181,064 |
| 2019-08 | 3 | 2,344,224 |
| 合计 | 11 | 8,575,221 |

清洗结果：保留 8,564,754 行（99.88%）；剔除 = 时长 > 4h（10,324 行）+ 站点信息缺失（143 行）+ 时间乱序（0）+ 越界坐标（0）。
时间范围：2019-05-01 ~ 2019-08-31；清洗后数据输出为 `data/processed/trips_clean.csv.gz`（含全部派生字段）。
