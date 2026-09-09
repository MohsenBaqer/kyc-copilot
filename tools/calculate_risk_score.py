"""
Tool: calculate_risk_score
Combines extraction, sanctions/PEP screening, and adverse
media results into one deterministic risk score, with a reason
attached to every contributing factor.
"""

import json

def _load_rubric_config(config_path: str = "data/risk_rubric_config.json") -> dict:
    with open(config_path, "r") as f:
        return json.load(f)


def calculate_risk_score(extraction_result: dict, sanctions_pep_result: dict,
                          adverse_media_result: dict,
                          config_path: str = "data/risk_rubric_config.json") -> dict:
    risk_points = 0
    factors = []

    config = _load_rubric_config(config_path)
    points = config["points"]
    thresholds = config["band_thresholds"]
    labels = config["band_labels"]

    if sanctions_pep_result.get("sanctions_hit"):
        risk_points += points["sanctions_hit"]
        factors.append({
            "factor": "Sanctions list match",
            "points": points["sanctions_hit"],
            "detail": f"{len(sanctions_pep_result['sanctions_matches'])} match(es) found on formal sanctions list(s).",
        })

    if sanctions_pep_result.get("pep_hit"):
        risk_points += points["pep_hit"]
        factors.append({
            "factor": "PEP match",
            "points": points["pep_hit"],
            "detail": f"{len(sanctions_pep_result['pep_matches'])} match(es) found on PEP list(s) — requires enhanced due diligence.",
        })

    severity = adverse_media_result.get("overall_severity", "none")
    media_points_map = {
      "high": points["adverse_media_high"], "medium": points["adverse_media_medium"], "low": points["adverse_media_low"], "none": 0,}
    media_points = media_points_map.get(severity, 0)
    if media_points > 0:
        risk_points += media_points
        factors.append({
            "factor": "Adverse media",
            "points": media_points,
            "detail": f"Adverse media found with '{severity}' severity.",
        })

    missing = extraction_result.get("missing_fields", [])
    if missing:
        risk_points += points["incomplete_documentation"]
        factors.append({
            "factor": "Incomplete documentation",
            "points": points["incomplete_documentation"],
            "detail": f"Missing fields: {', '.join(missing)} — screening results may be incomplete.",
        })

    if not factors:
        factors.append({
            "factor": "No red flags identified",
            "points": 0,
            "detail": "No sanctions, PEP, or adverse media matches found; documentation complete.",
        })

    risk_points = min(risk_points, 100)

    if risk_points >= thresholds["high_risk_min"]:
        band = labels["high"]
    elif risk_points >= thresholds["medium_risk_min"]:
        band = labels["medium"]
    else:
        band = labels["low"]

    return {
        "risk_score": risk_points,
        "band": band,
        "factors": factors,
    }


if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, ".")
    from tools.extract_document import extract_document
    from tools.screen_sanctions_pep import screen_sanctions_pep
    from tools.check_adverse_media import check_adverse_media

    path = sys.argv[1] if len(sys.argv) > 1 else "data/applicant_clean.txt"
    doc = extract_document(path)
    screening = screen_sanctions_pep(doc["applicant_name"], doc["business_name"])
    media = check_adverse_media(doc["applicant_name"], doc["business_name"])
    result = calculate_risk_score(doc, screening, media)
    print(json.dumps(result, indent=2))
