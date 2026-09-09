# 数据与方法

来源：[DfT Road safety open data](https://www.gov.uk/government/statistical-data-sets/road-safety-open-data)。数据采用 [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)。字段按来源页面的 Open dataset data guide 核对。

| 字段 | 本项目口径 |
| --- | --- |
| collision_severity | 1=死亡、2=重伤、3=轻伤；1/2 记为严重事故 |
| day_of_week | 1=周日、2=周一，…，7=周六；周末为 1/7 |
| light_conditions | 1=白天；4=夜间有照明；5/6=夜间无照明或灯未开；7=未知，排除 |
| first_road_class | 1 记为 Motorway；A(M) 不并入，解释限于这个分类口径 |
| speed_limit | 只保留 20/30/40/50/60/70 mph；不是碰撞发生时的车辆速度 |
| number_of_vehicles / casualties | 事故后信息，只用于描述 |

清洗同时检查时间、道路、天气、路面与城乡编码；原始日期保存在清洗表。当前分析排除道路类型 12（单行路/匝道合并类），未将其强行归入某个旧类别。

比例区间为大样本正态近似并截到 [0,1]；卡方使用未作 Yates 修正的统计量计算 Cramér's V；两比例检验使用正态尾概率。多重检验和空间聚集未完全处理，结果用于探索。

Logistic 模型 P(KSI=1 | 已记录事故, X)=1/(1+exp(-Xβ))，训练期估计系数，测试期只评分。参照类在 `modeling.py` 显式指定。`exp(β)` 为胜算比，胜算为 p/(1-p)。

严重度记录制度会影响跨年可比性，详见 [DfT 严重度调整说明](https://www.gov.uk/government/publications/guide-to-severity-adjustments-for-reported-road-casualty-statistics/guide-to-severity-adjustments-for-reported-road-casualties-great-britain)。本项目未应用这些调整，因此年度趋势只解释为本样本记录变化。
