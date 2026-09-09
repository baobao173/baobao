# baobao

我的 Python 项目和练习，主要是数据分析，也记录一些编程练习。

## 项目

| 项目 | 内容 |
| --- | --- |
| [零售销量预测与库存仿真](retail-demand-inventory/) | 交易数据清洗、周销量预测、补货策略比较 |
| [共享单车需求与站点流量分析](citibike-tide-and-dispatch/) | 骑行规律、天气相关分析、小时需求预测、站点净流量 |
| [道路交通事故严重性分析](road-safety-risk-analysis/) | 分组统计、逻辑回归、历史事故排查参考 |
| [猜数字游戏](guess-number/) | 命令行交互、输入检查与测试 |

每个项目都有自己的运行说明。分析报告、方法和数据说明放在各项目的 `docs/`，图表和结果表放在 `output/` 或 `outputs/`。

## 运行

```bash
git clone https://github.com/baobao173/baobao.git
cd baobao
```

进入对应项目目录后，按该目录的 README 安装依赖和运行。分析项目使用 Python 3.12；猜数字游戏只依赖标准库。

## 说明

数据分析使用公开数据。预测、相关分析和仿真各有适用范围，具体口径与局限见项目报告。

代码许可见 [LICENSE](LICENSE)，数据许可见各项目的数据说明。[检查记录](docs/review-notes.md)记录了本次修正与验证结果。
