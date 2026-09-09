# 数据说明

- 骑行：[Citi Bike System Data](https://citibikenyc.com/system-data)，2019 年 5—8 月；官方年度 ZIP 由脚本提取研究月份。
- 天气：[Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)，坐标 40.7794、-73.9692，`models=era5`，时区 `America/New_York`。
- 骑行数据按 Citi Bike 页面链接的使用条款使用；天气来源为 Open-Meteo / ECMWF ERA5，按其署名要求注明来源。代码许可与数据许可分开。

| 字段 | 含义 |
| --- | --- |
| start_time / end_time | 实际借出 / 归还时间 |
| start_station_id / end_station_id | 起终站编号；聚合以编号为键 |
| duration_sec | 行程时长，秒 |
| user_type | Subscriber / Customer，不能直接认定出行目的 |
| rides | 一个小时内的出发次数 |
| net_morning | 工作日 7:00—9:59 借出次数减同期归还次数 |
| temp_c / precip_mm / wind_kmh | 温度、小时降水和风速 |

骑行时间按纽约本地时间处理；研究月份没有夏令时切换。小时表补齐零记录时段，零记录不等于已经证明没有潜在需求。站点图的属性采用同一编号最后出现的记录。

`data/raw/` 保存下载，`data/processed/` 保存清洗和聚合表，两者不提交 Git。清洗计数在 `output/results/cleaning.json`。完整流水线可以重建结果。
