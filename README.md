# baobao

> **baobao173 的个人项目仓库** —— Python 数据分析 与 入门练习 的合集
>
> 本仓库收纳多个**彼此独立**的子项目，每个子项目各占一个文件夹、各有自己的 README，
> 点击下方"入口"即可直接进入对应项目。

## 项目导航

| 项目 | 一句话简介 | 入口 |
|---|---|---|
| **猜数字游戏** | Python 入门小游戏（命令行 + 单元测试） | [guess-number/](https://github.com/baobao173/baobao/tree/main/guess-number) |
| **共享单车潮汐与智能调度** | 856 万条骑行数据的 运营分析 + 需求预测 + 调度决策 | [citibike-tide-and-dispatch/](https://github.com/baobao173/baobao/tree/main/citibike-tide-and-dispatch) |

## 仓库结构

```
baobao/
├── README.md                    仓库门户（本文件）
├── .gitignore / .gitattributes  通用规范
├── LICENSE                      仓库级许可（版权人 baobao173）
├── guess-number/                子项目一：猜数字游戏
│   ├── README.md
│   ├── guess_number.py
│   └── test_guess_number.py
└── citibike-tide-and-dispatch/  子项目二：共享单车分析
    ├── README.md / LICENSE / requirements.txt
    ├── docs/     # 完整报告、数据字典、CV 素材、里程碑
    ├── src/      # 源码（下载/清洗/分析/建模/绘图）
    ├── scripts/  # 各阶段分析脚本 + 一键复现
    └── output/   # 14 张结果图 + 结果表
```

---

## 项目一：猜数字游戏（guess-number）

最基础的 Python 入门小项目：程序在 1~100 之间随机选一个数，玩家在终端里不断输入猜测，直到猜中为止。

- **运行**：`python guess_number.py`
- **测试**：`python -m unittest test_guess_number -v`
- **入口**：[回到仓库查看](https://github.com/baobao173/baobao/tree/main/guess-number) · [子项目 README](https://github.com/baobao173/baobao/blob/main/guess-number/README.md)

---

## 项目二：城市共享单车"潮汐"分析与智能调度决策（citibike-tide-and-dispatch）

> 一句话：**共享单车最贵的不是车，是车放错了地方。**
> 用纽约 Citi Bike 官方 856 万条骑行记录，回答"调度中心每天早上该往哪些站点补多少车"。

| 环节 | 关键数字 |
|---|---|
| 数据 | Citi Bike 官方 8,575,221 → 8,564,754 行（99.88%）· 840 站 · ERA5 逐时气象 |
| 时空规律 | 工作日"早8晚18"双峰 vs 周末午后单峰（统计检验 p<0.01） |
| 潮汐量化 | 工作日净迁移 ≈ 4,700 辆/日；486 居住型 / 308 办公型站点 |
| 天气归因 | OLS R²=0.773：下雨 −41%/时、温度倒 U（顶点 25.8°C） |
| 需求预测 | 随机森林 MAE≈270 辆/时（约 9%）、R²=0.956，较基线改善 67% |
| 决策建议 | 早高峰前投放、平峰转运腾桩、雨天减运力 |

- **入口**：[子项目文件夹](https://github.com/baobao173/baobao/tree/main/citibike-tide-and-dispatch) ·
  [子项目 README](https://github.com/baobao173/baobao/blob/main/citibike-tide-and-dispatch/README.md) ·
  [完整报告](https://github.com/baobao173/baobao/blob/main/citibike-tide-and-dispatch/docs/report.md)

![潮汐双峰](citibike-tide-and-dispatch/output/figures/01_hourly_demand_weekday_weekend.png)

---

## 许可证

仓库级许可见 [LICENSE](https://github.com/baobao173/baobao/blob/main/LICENSE)（版权人 baobao173）；
共享单车子项目的具体许可证与数据版权说明见其子目录内的 `LICENSE`。
