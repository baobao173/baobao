"""生成轻量阅读 notebook；结果来自完整主流程，不重复训练。"""

from pathlib import Path
import nbformat as nbf

root = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# 零售销量预测与库存仿真\n\n读取 `run_analysis.py` 生成的结果表，展示商品样本、预测误差和补货策略。分析代码位于 `src/`。"
    ),
    nbf.v4.new_code_cell(
        "from pathlib import Path\nimport pandas as pd\nfrom IPython.display import display, Image\nroot = Path.cwd()\nif not (root / 'config.json').exists():\n    root = root.parent\nassert (root / 'config.json').exists()"
    ),
    nbf.v4.new_markdown_cell(
        "## 商品样本\n\n商品仅按训练期活跃度和销售额筛选，验证期和测试期沿用同一组商品。"
    ),
    nbf.v4.new_code_cell(
        "products = pd.read_csv(root / 'outputs/tables/selected_products.csv')\ndisplay(products.head())\ndisplay(Image(filename=str(root / 'outputs/figures/03_volatility.png')))"
    ),
    nbf.v4.new_markdown_cell(
        "## 预测结果\n\n比较上周销量、四周移动平均和岭回归在验证期与测试期的误差。"
    ),
    nbf.v4.new_code_cell(
        "scores = pd.read_csv(root / 'outputs/tables/forecast_metrics.csv')\ndisplay(scores)\ndisplay(Image(filename=str(root / 'outputs/figures/04_forecast.png')))"
    ),
    nbf.v4.new_markdown_cell(
        "## 补货策略\n\n策略 C 按验证期成本选择模型和安全库存系数，测试期锁定。成本使用假设单位。"
    ),
    nbf.v4.new_code_cell(
        "policies = pd.read_csv(root / 'outputs/tables/policy_comparison.csv')\ndisplay(policies.query('lead == 0 and penalty == 5'))\ndisplay(Image(filename=str(root / 'outputs/figures/07_tradeoff.png')))"
    ),
    nbf.v4.new_markdown_cell(
        "## 库存明细\n\n期初库存 + 本周到货 − 满足量 = 期末库存；需求 = 满足量 + 缺货量。明细表由主程序生成，不提交仓库。"
    ),
    nbf.v4.new_code_cell(
        "trace = pd.read_csv(root / 'outputs/tables/inventory_traces.csv')\nexample = trace.query(\"split == 'test' and model == 'moving_average' and factor == 1 and lead == 0\")\ndisplay(example.head(8))\nassert ((trace.opening + trace.arrivals - trace.fulfilled - trace.ending).abs() < 1e-8).all()"
    ),
    nbf.v4.new_markdown_cell(
        "## 结果解释\n\n预测误差、满足率和成本分别衡量不同方面的表现。仿真采用历史销量作为需求代理，交期与持有成本由情景设定，结论适用于这些假设。详细结果见[分析报告](../docs/analysis_report.md)。"
    ),
]
nb.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
}
(root / "notebooks").mkdir(exist_ok=True)
nbf.write(nb, root / "notebooks/01_exploration.ipynb")
