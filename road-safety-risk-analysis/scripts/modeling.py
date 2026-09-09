"""训练与情景评分共用同一设计矩阵，不使用事故后变量。"""

from pathlib import Path
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parent.parent
FEATURES = [
    "light",
    "weather",
    "road_type",
    "area",
    "speed_limit",
    "is_motorway",
    "is_weekend",
    "period",
]
BASE = {
    "light": "白天",
    "weather": "晴",
    "road_type": "单幅路",
    "area": "城市",
    "period": "白天 10-15",
}


def load_data():
    return pd.read_csv(
        ROOT / "data/processed/accidents_clean.csv.gz", dtype={"collision_index": str}
    )


def design(df):
    x = pd.get_dummies(df[FEATURES], columns=list(BASE), dtype=float)
    x = x.drop(
        columns=[f"{col}_{value}" for col, value in BASE.items()], errors="ignore"
    )
    x.insert(0, "const", 1.0)
    return x.astype(float)


def fit_history(df):
    train = df[df.year.isin([2021, 2022, 2023])].copy()
    test = df[df.year == 2024].copy()
    x = design(train)
    model = sm.Logit(train.is_severe, x).fit(disp=False, maxiter=100)
    if not model.mle_retvals["converged"]:
        raise RuntimeError("Logistic model did not converge")
    return model, x.columns, train, test


def score(model, columns, df):
    x = design(df).reindex(columns=columns, fill_value=0.0)
    return model.predict(x)
