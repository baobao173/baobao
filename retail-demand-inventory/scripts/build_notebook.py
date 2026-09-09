"""生成轻量阅读 notebook；结果来自完整主流程，不重复训练。"""

from pathlib import Path
import nbformat as nbf

root = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# 零售销量预测与库存决策\n先运行 `run_analysis.py`，再依次阅读。核心实现保留在 src 中。"
    ),
    nbf.v4.new_code_cell(
        "from pathlib import Path\nimport pandas as pd\nfrom IPython.display import display, Image\nroot = Path.cwd()\nif not (root / 'config.json').exists():\n    root = root.parent\nassert (root / 'config.json').exists()"
    ),
    nbf.v4.new_markdown_cell(
        "## 1. 商品样本\n只在训练期按活跃度和销售额选样本。思考：用全时期选择会造成什么偏差？"
    ),
    nbf.v4.new_code_cell(
        "products = pd.read_csv(root / 'outputs/tables/selected_products.csv')\ndisplay(products.head())\ndisplay(Image(filename=str(root / 'outputs/figures/03_volatility.png')))"
    ),
    nbf.v4.new_markdown_cell(
        "## 2. 预测\n比较验证和测试，查看移动平均与岭回归能否稳定超越朴素规则。"
    ),
    nbf.v4.new_code_cell(
        "scores = pd.read_csv(root / 'outputs/tables/forecast_metrics.csv')\ndisplay(scores)\ndisplay(Image(filename=str(root / 'outputs/figures/04_forecast.png')))"
    ),
    nbf.v4.new_markdown_cell(
        "## 3. 补货决策\nC 在验证期选择，测试期不重新选择。成本为假设单位，不是实际利润。"
    ),
    nbf.v4.new_code_cell(
        "policies = pd.read_csv(root / 'outputs/tables/policy_comparison.csv')\ndisplay(policies.query('lead == 0 and penalty == 5'))\ndisplay(Image(filename=str(root / 'outputs/figures/07_tradeoff.png')))"
    ),
    nbf.v4.new_markdown_cell(
        "## 4. 手工检查库存守恒\n可用库存 − 满足需求 = 期末库存；需求 = 满足量 + 缺货量。"
    ),
    nbf.v4.new_code_cell(
        "trace = pd.read_csv(root / 'outputs/tables/inventory_traces.csv')\nexample = trace.query(\"split == 'test' and model == 'moving_average' and factor == 1 and lead == 0\")\ndisplay(example.head(8))\nassert ((trace.opening + trace.arrivals - trace.fulfilled - trace.ending).abs() < 1e-8).all()"
    ),
    nbf.v4.new_markdown_cell(
        "## 5. 讨论\n1. 为什么成本最优方案未必有最低 MAE？\n2. 验证选择是否在测试期保持优势？\n3. 没有实际库存，结论能推广到哪里？\n\n完整回答及实际结论见 docs/analysis_report.md。"
    ),
]
nb.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
}
(root / "notebooks").mkdir(exist_ok=True)
nbf.write(nb, root / "notebooks/01_exploration.ipynb")
