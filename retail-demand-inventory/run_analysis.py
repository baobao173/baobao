"""从项目任意工作目录调用本文件，生成全部分析结果。"""

import json
from pathlib import Path
from src.prepare_data import prepare
from src.analyze import describe_business
from src.forecast import backtest, metrics
from src.inventory import evaluate, choose_policies
from src.plot_results import plot_all
from src.report import write_report


def main():
    root = Path(__file__).resolve().parent
    for name in ["data/processed", "outputs/tables", "outputs/figures", "docs"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if config["base_penalty"] not in config["shortage_penalties"]:
        raise ValueError("base_penalty 必须出现在 shortage_penalties 中。")
    if 1 not in config["safety_factors"]:
        raise ValueError("safety_factors 必须包含 1，供 A/B 固定基准使用。")
    if min(config["test_weeks"], config["validation_weeks"], config["n_products"]) <= 0:
        raise ValueError("测试周数、验证周数和商品数必须为正。")
    print("1/5 Read and clean official data", flush=True)
    weekly, selected, totals, contribution, quality = prepare(root, config)
    print("2/5 Time-ordered forecasting", flush=True)
    predictions = backtest(weekly, config)
    scores, product_scores = metrics(predictions)
    business, phases = describe_business(weekly, selected, contribution, predictions)
    phases.to_csv(root / "outputs/tables/time_splits.csv", index=False)
    (root / "outputs/tables/business_summary.json").write_text(
        json.dumps(business, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "outputs/tables/run_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("3/5 Inventory simulation and validation selection", flush=True)
    results, traces = evaluate(predictions, config)
    policies = choose_policies(results, config)
    for name, df in [
        ("predictions", predictions),
        ("forecast_metrics", scores),
        ("product_metrics", product_scores),
        ("inventory_grid", results),
        ("inventory_traces", traces),
        ("policy_comparison", policies),
    ]:
        df.to_csv(root / f"outputs/tables/{name}.csv", index=False)
    print("4/5 Figures", flush=True)
    plot_all(
        root,
        weekly,
        selected,
        totals,
        contribution,
        predictions,
        scores,
        results,
        traces,
        policies,
        config,
    )
    print("5/5 Report", flush=True)
    write_report(root, config, quality, scores, policies, predictions, business)
    print(scores.to_string(index=False))
    print(policies.query("lead == 0 and penalty == 5").to_string(index=False))


if __name__ == "__main__":
    main()
