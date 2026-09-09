"""
Tool: score_alternative_credit

Purpose: Deterministic, rules-based alternative credit scoring —
Hal's third pillar: "AI-driven alternative credit scoring,
accelerating access to finance with fairness and speed." Uses bank
transaction data instead of traditional credit bureau history.
NO LLM — must be reproducible and explainable. Weights and band
thresholds are read from data/risk_rubric_config.json so they're
human-editable, same pattern as calculate_risk_score.
"""

import json


def _load_rubric_config(config_path: str = "data/risk_rubric_config.json") -> dict:
    with open(config_path, "r") as f:
        return json.load(f)


def _score_cash_flow_stability(metrics):
    net_values = list(metrics["monthly_net"].values())
    if not net_values:
        return 0.0, "No cash flow data available."
    negative_months = sum(1 for v in net_values if v < 0)
    share_negative = negative_months / len(net_values)
    if share_negative == 0:
        return 1.0, "Positive net cash flow in every month provided."
    elif share_negative < 0.34:
        return 0.6, f"Negative net cash flow in {negative_months} of {len(net_values)} months."
    else:
        return 0.2, f"Negative net cash flow in {negative_months} of {len(net_values)} months — recurring shortfall."


def _score_revenue_consistency(metrics):
    vol = metrics.get("revenue_volatility")
    if vol is None:
        return 0.4, "Insufficient months to calculate revenue volatility reliably."
    if vol < 0.10:
        return 1.0, f"Low revenue volatility ({vol:.1%}) — stable, predictable income."
    elif vol < 0.25:
        return 0.65, f"Moderate revenue volatility ({vol:.1%})."
    else:
        return 0.25, f"High revenue volatility ({vol:.1%}) — unpredictable income pattern."


def _score_data_completeness(metrics):
    months = metrics.get("months_covered", 0)
    if months >= 6:
        return 1.0, f"{months} months of transaction history — strong basis for assessment."
    elif months >= 3:
        return 0.6, f"{months} months of transaction history — usable but below the 6-month ideal."
    else:
        return 0.2, f"Only {months} month(s) of transaction history — insufficient for a confident assessment."


def _score_customer_concentration(metrics):
    pct = metrics.get("top_customer_pct")
    n_customers = metrics.get("num_distinct_customers", 0)
    if pct is None or n_customers < 2:
        return 0.3, "Insufficient distinct customers to assess concentration risk; treated conservatively."
    if pct < 0.40:
        return 1.0, f"Top customer accounts for {pct:.0%} of revenue — well diversified."
    elif pct < 0.65:
        return 0.6, f"Top customer accounts for {pct:.0%} of revenue — moderate concentration."
    else:
        return 0.2, f"Top customer accounts for {pct:.0%} of revenue — high concentration risk."


def _score_overdraft_distress(metrics):
    events = metrics.get("overdraft_events", 0)
    if events == 0:
        return 1.0, "No overdraft events detected."
    elif events <= 2:
        return 0.5, f"{events} overdraft event(s) detected — some liquidity stress."
    else:
        return 0.1, f"{events} overdraft events detected — recurring liquidity distress."


def score_alternative_credit(metrics: dict, config_path: str = "data/risk_rubric_config.json") -> dict:
    config = _load_rubric_config(config_path)
    weights = config["alternative_credit_weights"]
    thresholds = config["alternative_credit_band_thresholds"]
    labels = config["alternative_credit_band_labels"]

    scorers = {
        "cash_flow_stability": _score_cash_flow_stability,
        "revenue_consistency": _score_revenue_consistency,
        "data_completeness": _score_data_completeness,
        "customer_concentration": _score_customer_concentration,
        "overdraft_distress": _score_overdraft_distress,
    }

    breakdown = {}
    overall = 0.0
    for key, fn in scorers.items():
        raw_score, reason = fn(metrics)
        weighted_points = round(raw_score * weights[key], 1)
        breakdown[key] = {
            "raw_score": round(raw_score, 2),
            "weight": weights[key],
            "weighted_points": weighted_points,
            "reason": reason,
        }
        overall += weighted_points

    if overall >= thresholds["ready_min"]:
        band = labels["ready"]
    elif overall >= thresholds["conditional_min"]:
        band = labels["conditional"]
    else:
        band = labels["not_ready"]

    return {
        "overall_score": round(overall, 1),
        "band": band,
        "breakdown": breakdown,
        "data_quality_flags": metrics.get("data_quality_flags", []),
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from tools.extract_transactions import extract_from_transactions

    path = sys.argv[1] if len(sys.argv) > 1 else "data/sme_strong_transactions.csv"
    metrics = extract_from_transactions(path)
    result = score_alternative_credit(metrics)
    print(json.dumps(result, indent=2))