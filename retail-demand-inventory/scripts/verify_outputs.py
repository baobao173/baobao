"""对完整运行结果做独立一致性检查，不替代业务假设审查。"""

from pathlib import Path
import json
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[1]
p = pd.read_csv(root / "outputs/tables/predictions.csv", parse_dates=["week"])
t = pd.read_csv(root / "outputs/tables/inventory_traces.csv")
grid = pd.read_csv(root / "outputs/tables/inventory_grid.csv")
policies = pd.read_csv(root / "outputs/tables/policy_comparison.csv")
q = json.loads((root / "outputs/tables/data_quality.json").read_text(encoding="utf-8"))
config = json.loads(
    (root / "outputs/tables/run_config.json").read_text(encoding="utf-8")
)
assert not p.duplicated(["week", "product_id", "split", "model"]).any()
assert np.isfinite(p[["actual", "prediction", "sigma"]]).all().all()
assert (p[["actual", "prediction", "sigma"]] >= 0).all().all()
assert (
    p.query("split == 'validation'").week.max() < p.query("split == 'test'").week.min()
)
assert len(p) == q["products"] * (config["validation_weeks"] + config["test_weeks"]) * 3
assert (
    q["raw_rows"] - sum(v for k, v in q.items() if k.startswith("removed_"))
    == q["clean_rows"]
)
np.testing.assert_allclose(t.opening + t.arrivals - t.fulfilled, t.ending)
np.testing.assert_allclose(t.fulfilled + t.shortage, t.actual)
for r in policies.itertuples():
    subset = t[
        (t.split == "test")
        & (t.model == r.model)
        & (t.lead == r.lead)
        & (t.factor == r.factor)
    ]
    assert np.isclose(subset.ending.sum() + r.penalty * subset.shortage.sum(), r.cost)
    assert np.isclose(subset.fulfilled.sum() / subset.actual.sum(), r.fill_rate)
    if r.policy == "C":
        val = grid[
            (grid.split == "validation")
            & (grid.lead == r.lead)
            & (grid.penalty == r.penalty)
        ]
        chosen = val[(val.model == r.model) & (val.factor == r.factor)].iloc[0]
        assert np.isclose(chosen.cost, val.cost.min())
print(
    "PASS: prediction chronology, row counts, finite values, inventory conservation, policy selection, cost reconciliation"
)
