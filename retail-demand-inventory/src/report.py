"""报告数字从结果表生成，避免手写数字与运行结果不同步。"""


def write_report(root, config, quality, scores, policies, predictions, business):
    model_names = {
        "naive": "上周销量",
        "moving_average": "四周移动平均",
        "ridge": "岭回归",
    }
    test = scores.query("split == 'test'").sort_values("wape")
    base = policies[(policies.lead == 0) & (policies.penalty == config["base_penalty"])]
    a = base[base.policy == "A"].iloc[0]
    c = base[base.policy == "C"].iloc[0]
    change = (a.cost - c.cost) / a.cost
    direction = "下降" if change >= 0 else "上升"
    naive = test[test.model == "naive"].iloc[0]
    moving = test[test.model == "moving_average"].iloc[0]
    improvement = 1 - moving.wape / naive.wape
    error_direction = "降低" if improvement >= 0 else "上升"
    test_rows = predictions[predictions.split == "test"]
    dates = f"{test_rows.week.min():%Y-%m-%d} 至 {test_rows.week.max():%Y-%m-%d}（周一标签）"
    lines = [
        "# 零售销量预测与库存仿真",
        "",
        "## 研究问题",
        "能否用简单销量预测辅助每周补货？预测误差改善是否转化为更低库存成本？",
        "",
        "## 数据与样本",
        f"原始 {quality['raw_rows']:,} 行；清洗及完整周筛选后 {quality['clean_rows']:,} 行。研究 {config['country']} 市场，选取训练期活跃周占比至少 {config['min_active_share']:.0%} 的高销售额商品，共 {quality['products']} 个。周度区间 {quality['first_week']} 至 {quality['last_week']}，共 {quality['weeks']} 周。",
        "",
        "来源：Chen, D. (2012), [Online Retail II](https://doi.org/10.24432/C5CG6D), UCI。数据采用 CC BY 4.0。",
        "清洗保留客户编号缺失和疑似重复记录，避免在证据不足时删掉有效销量；取消/负数量、非正价格和不匹配五位数字加可选字母的商品代码被排除。代码规则可能漏掉有效特殊商品。异常批发大单保留，均值和回归可能受其影响。详见 data_quality.json。",
        "",
        "## 经营分析",
        f"训练期有 {business['training_products']:,} 个商品，其中销售额最高的 {business['products_for_80pct_sales']:,} 个（占 {business['share_products_for_80pct_sales']:.1%}）贡献了至少 80% 的正向销售额。所选 {quality['products']} 个常销商品贡献 {business['selected_sales_share']:.1%}，训练期销量变异系数中位数为 {business['median_selected_cv']:.2f}。高活跃度并不意味着销量稳定。",
        "",
        "![销售趋势](../outputs/figures/01_sales_trend.png)",
        "![销售贡献](../outputs/figures/02_contribution.png)",
        "![销量波动](../outputs/figures/03_volatility.png)",
        "",
        "经营含义：可优先对高贡献商品建立补货监控，但这些商品的波动水平仍有差异。销售额没有扣采购成本，不能据此排列盈利能力。年末零销量周可能与营业或记录状态有关，此数据不足以判定原因。",
        "",
        "## 验证设计",
        f"训练期截至 {quality['train_end_exclusive']}（不含），随后 {config['validation_weeks']} 周验证、最后 {config['test_weeks']} 周测试。测试区间 {dates}。每阶段开始时拟合各商品岭回归，阶段内参数固定，但每周特征更新为已经观察到的实际销量。alpha={config['ridge_alpha']} 预先固定；负预测截为零。没有使用随机切分。",
        "",
        "安全库存尺度是每阶段开始前 12 周销量标准差，并非已校准的预测区间；k 不对应正态分布服务概率。C 策略按各成本/提前期场景的验证成本选择模型和 k，测试期锁定。",
        "",
        "## 预测结果",
        "| 模型 | MAE（件/商品周） | WAPE |",
        "|---|---:|---:|",
    ]
    for row in test.itertuples():
        lines.append(f"| {model_names[row.model]} | {row.mae:.2f} | {row.wape:.2%} |")
    lines += [
        "",
        f"测试期 WAPE 最低的是{model_names[test.iloc[0].model]}。四周移动平均相对上周销量基准的 WAPE {error_direction} {abs(improvement):.2%}。策略 C 沿用验证期的选择；模型差异尚未做显著性检验。",
        "",
        "![预测误差](../outputs/figures/05_model_errors.png)",
        "",
        "## 库存决策结果",
        f"基础情景：提前期为零，单位期末库存每周成本设为 1，单位缺货惩罚设为 {config['base_penalty']}。成本是归一化情景单位，不是英镑。A=移动平均、k=1；B=岭回归、k=1；C=验证集选择。",
        "",
        "| 策略 | 模型 | k | 平均期末库存/商品周 | 数量满足率 | 情景总成本 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in base.itertuples():
        lines.append(
            f"| {row.policy} | {model_names[row.model]} | {row.factor:g} | {row.mean_inventory:.2f} | {row.fill_rate:.2%} | {row.cost:,.0f} |"
        )
    lines += [
        "",
        f"C 相对 A 的测试情景成本{direction} {abs(change):.2%}。验证期选出的组合为{model_names[c.model]}、k={c.factor:g}。成本、数量满足率与平均库存共同反映策略表现。",
        "",
        f"验证期平均销量为 {business['validation_mean_units']:.2f} 件/商品周，测试期为 {business['test_mean_units']:.2f}，变化 {business['test_vs_validation_growth']:+.1%}。两个阶段的需求水平不同，固定参数在测试期可能面临需求变化。当前分析未分离需求变化与其他因素各自的影响。",
        "",
        "![权衡](../outputs/figures/07_tradeoff.png)",
        "![敏感性](../outputs/figures/08_sensitivity.png)",
        "",
        "## 管理解释与局限",
        "",
        "- 固定安全库存比较 A/B 主要观察预测方法差异；A/C 同时包含方法与参数选择差异，不能归因于单一因素。",
        "- 1 周提前期使用两周平坦需求预测以及平方根时间缩放，仅为简化情景。不同周误差可能相关，缩放未得到统计校准。",
        "- 所有策略从空库存和空在途开始；提前期为 1 时第一周必然缺货。跨提前期比较包含这一启动效应，不能解释为纯提前期因果效应。",
        "- 销量作为外生需求代理，即使模拟缺货仍可观察历史销量；这相当于有外部需求记录的回放实验，真实业务中缺货会遮蔽需求。",
        "- 无交易周视为零，没有真实营业、缺货与停售状态；没有采购成本、仓储容量、最小订货量、退货再入库或供应限制。",
        "- 每件商品使用相同成本假设，未体现商品价值差异；期末库存没有清算或残值处理，在途库存只记录、不计持有成本。",
        f"- 测试期只有 {config['test_weeks']} 周，尚不能覆盖全年；模型差异和策略收益需要更多时间区间验证。",
        "- 训练期常销高贡献样本存在明确适用范围：不代表新品、长尾商品或中国当前零售市场。",
        "",
        "## 建议",
        "先建立简单规则基准，按缺货代价选择安全库存，再检查复杂一点的预测是否带来额外价值。上线前必须补充真实库存、交期和成本信息，并跨季节回测。",
        "",
    ]
    spaced = []
    for i, line in enumerate(lines):
        spaced.append(line)
        if line.startswith("#") and i + 1 < len(lines) and lines[i + 1]:
            spaced.append("")
    (root / "docs/analysis_report.md").write_text("\n".join(spaced), encoding="utf-8")
    # README 只更新结果区块，保留安装和阅读说明。
    readme = root / "README.md"
    content = readme.read_text(encoding="utf-8")
    start, end = "<!-- RESULTS_START -->", "<!-- RESULTS_END -->"
    result = (
        f'\n\n- 数据：{quality["raw_rows"]:,} 条原始交易，'
        f'{quality["products"]} 个常销商品，{quality["weeks"]} 个完整周。\n'
        f"- 预测：四周移动平均测试 WAPE 为 {moving.wape:.2%}，"
        f"较上周销量基准{error_direction} {abs(improvement):.1%}。\n"
        f"- 库存：基础情景下，验证期选出的补货策略在测试期的成本，"
        f"相较于移动平均、k=1 的基准{direction} {abs(change):.1%}。\n"
        "- 成本以仿真假设单位计量，参数与结果见[分析报告](docs/analysis_report.md)。\n\n"
    )
    if start in content and end in content:
        content = content.split(start)[0] + start + result + end + content.split(end)[1]
        readme.write_text(content, encoding="utf-8")
