# 道路交通事故严重性分析

用英国交通部 STATS19 2021—2024 年事故记录，分析已发生事故在不同光照、天气和道路条件下的严重程度差异，并用逻辑回归进行条件严重性排序。

## 结果

- 当前官方数据清洗后为 372,578 起事故。
- 2021—2023 年拟合，2024 年测试，ROC AUC 为 0.581，排序能力有限。
- 输出历史情景统计和分层评价，作为进一步核查的参考。数据没有无事故路段和交通流量，不能估计事故发生概率，也不据此触发交通信号。

![分组严重率](output/figures/fig3_severity_by_factors.png)

## 运行

推荐 Python 3.12。在本目录创建并激活虚拟环境后执行：

```bash
python -m pip install -r requirements.txt
python scripts/run_all.py
python -m unittest discover -s tests -v
```

首次运行下载 2021—2024 年事故表，约 80 MB。下载、清洗、统计、模型与结果输出按顺序执行。

## 文档

- [分析报告](docs/report.md)
- [数据与方法](docs/methodology.md)

`scripts/` 是分析代码，`output/` 保存图表和结果，`data/` 为本地生成的数据。代码使用 [MIT 许可](LICENSE)，数据来源与许可见方法说明。
