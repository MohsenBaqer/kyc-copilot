"""
Tool: lookup_public_info

Purpose: Given a name (person or company), searches the web for
publicly available identifying details and returns them as a
SUGGESTION.
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You search the web for publicly available information
about a named person or company, for KYC intake purposes.

Return ONLY valid JSON, no markdown fences, no preamble, in this shape:
{
  "subject_type": "person" or "company",
  "found_summary": "1-2 sentence plain-language summary of what you found",
  "suggested_fields": {
    "applicant_name": "string or null",
    "date_of_birth": "string or null",
    "nationality": "string or null",
    "business_name": "string or null",
    "business_registration_number": "string or null",
    "business_address": "string or null",
    "business_activity": "string or null"
  },
  "confidence_note": "a short honest note on how confident this match is, e.g. 'common name, multiple possible matches' or 'high confidence, well-documented public figure/entity'",
  "source_count": integer number of distinct sources referenced
}

Rules:
- If the name is ambiguous (common name, multiple plausible matches), say so
  explicitly in confidence_note rather than picking one arbitrarily.
- Only include fields you found real, specific evidence for. Never guess or
  infer a plausible-sounding value.
- Registration numbers and precise addresses are rarely public for private
  individuals — leave them null unless genuinely found.
"""


def lookup_public_info(name: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": f"Look up public information about: {name}"}],
    )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    raw_output = "".join(text_blocks).strip()

    if raw_output.startswith("```"):
        raw_output = raw_output.split("```")[1]
        if raw_output.startswith("json"):
            raw_output = raw_output[4:]
        raw_output = raw_output.strip()

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return {
            "subject_type": "unknown",
            "found_summary": "Could not parse a structured result.",
            "suggested_fields": {},
            "confidence_note": "Lookup failed to return usable data.",
            "source_count": 0,
        }


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "Bill Gates"
    result = lookup_public_info(name)
    print(json.dumps(result, indent=2))
