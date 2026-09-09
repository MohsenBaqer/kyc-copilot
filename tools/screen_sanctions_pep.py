"""
Tool: screen_sanctions_pep

Purpose: Checks an applicant's name and business name against real
sanctions and PEP data via the OpenSanctions API.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("OPENSANCTIONS_API_KEY")
MATCH_URL = "https://api.opensanctions.org/match/default"


def _query_opensanctions(name: str, birth_date: str = None, nationality: str = None,
                          schema: str = "Person") -> list:
    properties = {"name": [name]}
    if birth_date:
        properties["birthDate"] = [birth_date]
    if nationality:
        properties["nationality"] = [nationality]

    payload = {
        "queries": {
            "q1": {
                "schema": schema,
                "properties": properties
            }
        }
    }
    headers = {"Authorization": API_KEY}

    response = requests.post(MATCH_URL, json=payload, headers=headers, timeout=15)
    response.raise_for_status()

    data = response.json()
    return data.get("responses", {}).get("q1", {}).get("results", [])


def screen_sanctions_pep(applicant_name: str, business_name: str = None,
                          date_of_birth: str = None, nationality: str = None) -> dict:
    names_to_check = [n for n in [applicant_name, business_name] if n]

    sanctions_matches = []
    pep_matches = []

    for name in names_to_check:
        # Only pass DOB/nationality when checking the person's name,
        # not the business name (those fields don't apply to companies)
        is_person_name = (name == applicant_name)
        results = _query_opensanctions(
            name,
            birth_date=date_of_birth if is_person_name else None,
            nationality=nationality if is_person_name else None,
            schema="Person" if is_person_name else "Organization",
        )

        for result in results:
            score = result.get("score", 0)
            if score < 0.85:
                continue

            topics = result.get("properties", {}).get("topics", [])
            matched_name = result.get("caption", name)

            if any("sanction" in t for t in topics):
                sanctions_matches.append({
                    "matched_name": matched_name,
                    "checked_against": name,
                    "score": round(score, 2),
                    "topics": topics,
                })

            if any("role.pep" in t for t in topics):
                pep_matches.append({
                    "matched_name": matched_name,
                    "checked_against": name,
                    "score": round(score, 2),
                    "topics": topics,
                })

    return {
        "names_checked": names_to_check,
        "sanctions_hit": len(sanctions_matches) > 0,
        "sanctions_matches": sanctions_matches,
        "pep_hit": len(pep_matches) > 0,
        "pep_matches": pep_matches,
    }

if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, ".")
    from tools.extract_document import extract_document

    path = sys.argv[1] if len(sys.argv) > 1 else "data/applicant_clean.txt"
    doc = extract_document(path)
    result = screen_sanctions_pep(
        doc["applicant_name"],
        doc.get("business_name"),
        doc.get("date_of_birth"),
        doc.get("nationality"),
    )
    print(json.dumps(result, indent=2))
