"""
Tool: extract_document

Purpose: Turns a raw KYC intake document (any freeform text) into
structured fields the rest of the pipeline can use. Uses Claude to
handle arbitrary formatting/wording rather than rigid regex matching.
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

REQUIRED_FIELDS = [
    "applicant_name",
    "date_of_birth",
    "nationality",
    "business_name",
    "business_registration_number",
    "business_address",
    "business_activity",
    "ownership",
    "source_of_funds",
]

SYSTEM_PROMPT = f"""You extract structured KYC intake fields from a business
registration or onboarding document. The document may be in any format or
wording — do not expect exact field labels.

Extract these fields if present: {', '.join(REQUIRED_FIELDS)}

Rules:
- If a field is genuinely not present in the document, set its value to null.
  NEVER guess, infer, or invent a value that isn't actually in the text.
- Respond ONLY in valid JSON, no markdown fences, no preamble, with this
  exact shape:
{{
  "applicant_name": "string or null",
  "date_of_birth": "string or null",
  "nationality": "string or null",
  "business_name": "string or null",
  "business_registration_number": "string or null",
  "business_address": "string or null",
  "business_activity": "string or null",
  "ownership": "string or null",
  "source_of_funds": "string or null"
}}
"""


class ExtractionError(Exception):
    pass


def extract_document(file_path: str) -> dict:
    try:
        with open(file_path, "r") as f:
            raw_text = f.read()
    except Exception as e:
        raise ExtractionError(f"Could not read document: {e}")

    if not raw_text.strip():
        raise ExtractionError("Document is empty.")

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": raw_text}],
    )

    raw_output = response.content[0].text.strip()

    # Defensive cleanup: some responses wrap JSON in markdown fences
    # despite instructions not to. Strip them if present.
    if raw_output.startswith("```"):
        raw_output = raw_output.split("```")[1]
        if raw_output.startswith("json"):
            raw_output = raw_output[4:]
        raw_output = raw_output.strip()
        
    try:
        extracted = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ExtractionError(f"Model did not return valid JSON: {raw_output[:200]}")

    missing_fields = [field for field in REQUIRED_FIELDS if not extracted.get(field)]

    extracted["missing_fields"] = missing_fields
    extracted["extraction_complete"] = len(missing_fields) == 0

    return extracted


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/applicant_clean.txt"
    try:
        result = extract_document(path)
        print(json.dumps(result, indent=2))
    except ExtractionError as e:
        print(json.dumps({"error": str(e)}, indent=2))
