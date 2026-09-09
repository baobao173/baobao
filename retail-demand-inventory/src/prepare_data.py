"""读取官方文件，保留真实大订单，不将退货当成负需求。"""

import hashlib
import json
import zipfile
from urllib.request import urlretrieve

import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/502/online%2Bretail%2Bii.zip"


def prepare(root, config):
    raw = root / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    archive = raw / "online_retail_ii.zip"
    if not archive.exists():
        urlretrieve(URL, archive)
    with zipfile.ZipFile(archive) as z:
        name = next(n for n in z.namelist() if n.endswith(".xlsx"))
        with z.open(name) as f:
            sheets = pd.read_excel(f, sheet_name=None)
    df = pd.concat(sheets.values(), ignore_index=True)
    df = df.rename(
        columns={
            "Invoice": "invoice_id",
            "StockCode": "product_id",
            "Description": "description",
            "Quantity": "quantity",
            "InvoiceDate": "date",
            "Price": "price",
            "Customer ID": "customer_id",
            "Country": "country",
        }
    )
    quality = {
        "raw_rows": len(df),
        "missing_customer": int(df.customer_id.isna().sum()),
        "duplicate_candidates_retained": int(df.duplicated().sum()),
        "source_url": URL,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    df["date"] = pd.to_datetime(df.date, errors="coerce")
    df["product_id"] = df.product_id.astype(str).str.strip()
    cancellation = df.invoice_id.astype(str).str.upper().str.startswith("C") | (
        df.quantity < 0
    )
    quality["cancel_or_negative_rows"] = int(cancellation.sum())
    masks = {
        "not_cancelled": ~cancellation,
        "positive_quantity_price": (df.quantity > 0) & (df.price > 0),
        "valid_date": df.date.notna(),
        "selected_market": df.country.eq(config["country"]),
        "physical_code_pattern": df.product_id.str.fullmatch(
            r"\d{5}[A-Za-z]*", na=False
        ),
    }
    for label, mask in masks.items():
        before = len(df)
        df = df.loc[mask.reindex(df.index)].copy()
        quality["removed_" + label] = before - len(df)
    # 全数据时间边界的首尾不完整周排除；周标签是周一。
    dates = pd.concat([s["InvoiceDate"] for s in sheets.values()])
    first, last = pd.to_datetime(dates).min(), pd.to_datetime(dates).max()
    start = first.normalize() + pd.Timedelta(days=(7 - first.weekday()) % 7)
    end = last.normalize() - pd.Timedelta(days=last.weekday())
    before = len(df)
    df = df.loc[(df.date >= start) & (df.date < end)].copy()
    quality["removed_incomplete_weeks"] = before - len(df)
    df["week"] = df.date.dt.to_period("W-SUN").dt.start_time
    df["revenue"] = df.quantity * df.price
    weeks = pd.date_range(start, end - pd.Timedelta(weeks=1), freq="W-MON")
    train_end = weeks[-config["test_weeks"] - config["validation_weeks"]]
    train = df[df.week < train_end]
    n_train = int((weeks < train_end).sum())
    if n_train < 20:
        raise ValueError("训练期至少需要 20 个完整周，请缩短验证或测试期。")
    stats = train.groupby("product_id").agg(
        revenue=("revenue", "sum"),
        active_weeks=("week", "nunique"),
        description=("description", "first"),
    )
    stats["active_share"] = stats.active_weeks / n_train
    selected = (
        stats[stats.active_share >= config["min_active_share"]]
        .sort_values("revenue", ascending=False)
        .head(config["n_products"])
    )
    if selected.empty:
        raise ValueError("筛选后没有商品，请检查市场名称和活跃周阈值。")
    weekly = (
        df[df.product_id.isin(selected.index)]
        .groupby(["week", "product_id"])
        .quantity.sum()
        .unstack(fill_value=0)
    )
    weekly = weekly.reindex(index=weeks, columns=selected.index, fill_value=0)
    weekly.index.name = "week"
    selected["mean"] = weekly.loc[weekly.index < train_end].mean()
    selected["std"] = weekly.loc[weekly.index < train_end].std()
    selected["cv"] = selected["std"] / selected["mean"]
    all_contribution = stats.sort_values("revenue", ascending=False).copy()
    all_contribution["cumulative_share"] = (
        all_contribution.revenue.cumsum() / all_contribution.revenue.sum()
    )
    all_contribution["abc"] = all_contribution.cumulative_share.map(
        lambda x: "A" if x <= 0.8 else ("B" if x <= 0.95 else "C")
    )
    totals = (
        df.groupby("week")[["quantity", "revenue"]].sum().reindex(weeks, fill_value=0)
    )
    quality.update(
        clean_rows=len(df),
        weeks=len(weeks),
        products=len(selected),
        train_end_exclusive=str(train_end.date()),
        first_week=str(weeks[0].date()),
        last_week=str(weeks[-1].date()),
    )
    (root / "outputs/tables/data_quality.json").write_text(
        json.dumps(quality, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    weekly.to_csv(root / "data/processed/weekly_sales.csv")
    selected.to_csv(root / "outputs/tables/selected_products.csv")
    all_contribution.to_csv(root / "outputs/tables/product_contribution.csv")
    totals.to_csv(root / "outputs/tables/weekly_totals.csv", index_label="week")
    return weekly, selected, totals, all_contribution, quality
