"""
Tool: extract_transactions

Purpose: Parses raw bank transaction CSVs into structured financial
metrics for alternative credit scoring — using transaction history
as an alternative data source in place of traditional credit bureau
history. Does no judgment — only extraction.
"""

import pandas as pd


class ExtractionError(Exception):
    pass


def extract_from_transactions(csv_path: str) -> dict:
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        raise ExtractionError(f"Could not read CSV file: {e}")

    required_cols = {"date", "description", "amount", "type"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ExtractionError(f"Missing required columns: {missing}")

    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")

    months_covered = df["month"].nunique()
    if months_covered < 1:
        raise ExtractionError("No valid dated transactions found.")

    monthly = df.groupby(["month", "type"])["amount"].sum().unstack(fill_value=0)
    monthly_revenue = monthly.get("credit", pd.Series(dtype=float)).abs()
    monthly_expenses = monthly.get("debit", pd.Series(dtype=float)).abs()
    monthly_net = monthly_revenue.subtract(monthly_expenses, fill_value=0)

    credits = df[df["type"] == "credit"].copy()
    customer_totals = credits.groupby("description")["amount"].sum().sort_values(ascending=False)
    top_customer_pct = None
    if customer_totals.sum() > 0:
        top_customer_pct = round(float(customer_totals.iloc[0] / customer_totals.sum()), 3)

    result = {
        "months_covered": int(months_covered),
        "monthly_revenue": {str(k): round(float(v), 2) for k, v in monthly_revenue.items()},
        "monthly_expenses": {str(k): round(float(v), 2) for k, v in monthly_expenses.items()},
        "monthly_net": {str(k): round(float(v), 2) for k, v in monthly_net.items()},
        "avg_monthly_revenue": round(float(monthly_revenue.mean()), 2) if len(monthly_revenue) else 0,
        "revenue_volatility": round(float(monthly_revenue.std() / monthly_revenue.mean()), 3)
            if len(monthly_revenue) > 1 and monthly_revenue.mean() > 0 else None,
        "top_customer_pct": top_customer_pct,
        "num_distinct_customers": int(customer_totals.shape[0]),
        "overdraft_events": int(df["description"].str.contains("overdraft", case=False, na=False).sum()),
        "data_quality_flags": [],
    }

    if months_covered < 3:
        result["data_quality_flags"].append(
            f"Only {months_covered} month(s) of transaction history provided; at least 3 recommended."
        )
    if result["num_distinct_customers"] < 2:
        result["data_quality_flags"].append(
            "Fewer than 2 distinct customers identified; concentration risk cannot be reliably assessed."
        )

    return result


if __name__ == "__main__":
    import json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/sme_strong_transactions.csv"
    try:
        data = extract_from_transactions(path)
        print(json.dumps(data, indent=2))
    except ExtractionError as e:
        print(json.dumps({"error": str(e)}, indent=2))