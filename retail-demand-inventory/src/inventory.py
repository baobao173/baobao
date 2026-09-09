"""每周初订货，L=0 本周到、L=1 下周到；缺货当期流失。"""

import math
import pandas as pd


def simulate(group, factor, lead=0):
    stock = 0.0  # 所有方案从相同的空库存开始；L=1 首周缺货属于启动效应。
    pipeline = {}
    rows = []
    for i, row in enumerate(group.sort_values("week").itertuples()):
        opening = stock
        arrivals = pipeline.pop(i, 0.0)
        stock += arrivals
        # 两周场景采用平坦预测：第二周预测等于第一周，不读取未来实际值。
        target = math.ceil(
            (lead + 1) * row.prediction + factor * row.sigma * math.sqrt(lead + 1)
        )
        order = max(0, target - stock - sum(pipeline.values()))
        if lead == 0:
            stock += order
            arrivals += order
        else:
            pipeline[i + lead] = pipeline.get(i + lead, 0) + order
        fulfilled = min(stock, row.actual)
        shortage = row.actual - fulfilled
        stock -= fulfilled
        rows.append(
            dict(
                week=row.week,
                product_id=row.product_id,
                actual=row.actual,
                opening=opening,
                arrivals=arrivals,
                order=order,
                fulfilled=fulfilled,
                shortage=shortage,
                ending=stock,
                on_order=sum(pipeline.values()),
            )
        )
    return pd.DataFrame(rows)


def evaluate(predictions, config):
    results = []
    traces = []
    for (split, model), group in predictions.groupby(["split", "model"]):
        for lead in [0, 1]:
            for factor in config["safety_factors"]:
                trace = pd.concat(
                    [simulate(g, factor, lead) for _, g in group.groupby("product_id")],
                    ignore_index=True,
                )
                trace = trace.assign(split=split, model=model, lead=lead, factor=factor)
                traces.append(trace)
                for penalty in config["shortage_penalties"]:
                    results.append(
                        dict(
                            split=split,
                            model=model,
                            lead=lead,
                            factor=factor,
                            penalty=penalty,
                            mean_inventory=trace.ending.mean(),
                            shortage=trace.shortage.sum(),
                            fill_rate=trace.fulfilled.sum() / trace.actual.sum(),
                            cost=trace.ending.sum() + penalty * trace.shortage.sum(),
                        )
                    )
    return pd.DataFrame(results), pd.concat(traces, ignore_index=True)


def choose_policies(results, config):
    """每个成本/提前期场景在验证集选 C，之后锁定并评估测试集。"""
    choices = []
    for (lead, penalty), val in results.query("split == 'validation'").groupby(
        ["lead", "penalty"]
    ):
        best = val.sort_values(["cost", "model", "factor"]).iloc[0]
        settings = [
            ("A", "moving_average", 1.0),
            ("B", "ridge", 1.0),
            ("C", best.model, best.factor),
        ]
        for policy, model, factor in settings:
            row = (
                results.query(
                    "split == 'test' and lead == @lead and penalty == @penalty and model == @model and factor == @factor"
                )
                .iloc[0]
                .to_dict()
            )
            choices.append(dict(row, policy=policy))
    return pd.DataFrame(choices)
