"""
Tool: check_adverse_media

Purpose: Checks an applicant's name and business name against real
news coverage via NewsAPI.org (free tier, local/dev use). Flags
articles whose headline or description contains adverse-sounding
keywords, categorized by severity.

Limitation, worth being explicit about: keyword matching is a
simplification, not true classification — a real adverse media
provider uses NLP/ML categorization aligned to FATF risk categories.
This is a transparent, explainable stand-in for that.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("NEWSAPI_KEY")
NEWSAPI_URL = "https://newsapi.org/v2/everything"

ADVERSE_KEYWORDS = {
    "high": ["fraud", "money laundering", "sanctions", "terrorism", "embezzlement", "bribery"],
    "medium": ["investigation", "lawsuit", "arrested", "charged", "indicted", "scandal"],
    "low": ["fine", "penalty", "violation", "dispute", "complaint"],
}


def _query_newsapi(name: str) -> list:
    params = {
        "q": f'"{name}"',
        "apiKey": API_KEY,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": 20,
    }
    response = requests.get(NEWSAPI_URL, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()
    return data.get("articles", [])


def _classify_severity(text: str) -> str:
    text_lower = text.lower()
    for severity in ["high", "medium", "low"]:
        for keyword in ADVERSE_KEYWORDS[severity]:
            if keyword in text_lower:
                return severity
    return None


def check_adverse_media(applicant_name: str, business_name: str = None) -> dict:
    names_to_check = [n for n in [applicant_name, business_name] if n]

    hits = []

    for name in names_to_check:
        articles = _query_newsapi(name)

        for article in articles:
            title = article.get("title") or ""
            description = article.get("description") or ""
            combined_text = f"{title} {description}"

            severity = _classify_severity(combined_text)
            if severity:
                hits.append({
                    "name": name,
                    "headline": title,
                    "source": (article.get("source") or {}).get("name", "unknown"),
                    "date": article.get("publishedAt", "unknown"),
                    "url": article.get("url", ""),
                    "severity": severity,
                })

    severities = [h["severity"] for h in hits]
    if "high" in severities:
        overall_severity = "high"
    elif "medium" in severities:
        overall_severity = "medium"
    elif "low" in severities:
        overall_severity = "low"
    else:
        overall_severity = "none"

    return {
        "names_checked": names_to_check,
        "adverse_media_hit": len(hits) > 0,
        "overall_severity": overall_severity,
        "hits": hits,
    }


if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, ".")
    from tools.extract_document import extract_document

    path = sys.argv[1] if len(sys.argv) > 1 else "data/applicant_clean.txt"
    doc = extract_document(path)
    result = check_adverse_media(doc["applicant_name"], doc.get("business_name"))
    print(json.dumps(result, indent=2))