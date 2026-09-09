# 数据说明

来源：Chen, D. (2012), Online Retail II, UCI Machine Learning Repository。

- 官方页面：https://archive.ics.uci.edu/dataset/502/online+retail+ii
- DOI：https://doi.org/10.24432/C5CG6D
- 下载：https://archive.ics.uci.edu/static/public/502/online%2Bretail%2Bii.zip
- 许可证：CC BY 4.0，https://creativecommons.org/licenses/by/4.0/
- 获取日期：2026-09-09。下载 ZIP 的 SHA256 由每次运行记录在 `outputs/tables/data_quality.json`。

原始记录涵盖 2009-12-01 至 2011-12-09，英国礼品零售商，含批发客户。原始 ZIP 留在 raw，不提交 Git。processed 是脚本生成的商品周销量，不提交 Git；outputs 中公开的是聚合或模型衍生记录，无客户标识。

| 原始字段 | 统一字段 | 口径 |
|---|---|---|
| Invoice | invoice_id | 订单编号，C 开头为取消 |
| StockCode | product_id | 商品编号，按字符串处理 |
| Description | description | 商品描述 |
| Quantity | quantity | 件数 |
| InvoiceDate | date | 原始本地交易时间，不作时区转换 |
| Price | price | 销售单价，英镑，不是采购成本 |
| Customer ID | customer_id | 客户编号，允许缺失 |
| Country | country | 客户国家 |

销售额=正向数量×正销售价，不扣退款，不等于净收入或利润。销量=正向销售数量，不是真实未约束需求。周为周一到周日，标签为周一。

清洗计数按顺序互斥记录；原始取消/负数量和疑似重复计数为独立诊断，不能与清洗计数直接相加。首尾不完整周筛选在市场与商品代码过滤之后。疑似重复不删除；异常大单不截尾。每个决定均可修改，但应报告对结果的影响。
