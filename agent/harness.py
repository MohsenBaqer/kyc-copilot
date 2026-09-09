"""
Agent harness: the orchestration loop that talks to Claude, executes
tool calls, and feeds results back — until Claude gives a final answer.
"""

import json
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

sys.path.insert(0, ".")

from agent.tool_schemas import TOOLS
from agent.audit_log import AuditLog
from tools.extract_document import extract_document
from tools.screen_sanctions_pep import screen_sanctions_pep
from tools.check_adverse_media import check_adverse_media
from tools.calculate_risk_score import calculate_risk_score
from tools.extract_transactions import extract_from_transactions
from tools.score_alternative_credit import score_alternative_credit

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-5"


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Takes a tool name and arguments (both decided by Claude) and runs
    the matching Python function. This is the ONE place in the whole
    system where a string name gets turned into an actual function call.
    """
    if tool_name == "extract_document":
        return extract_document(tool_input["file_path"])

    elif tool_name == "screen_sanctions_pep":
        return screen_sanctions_pep(
            tool_input["applicant_name"],
            tool_input.get("business_name"),
            tool_input.get("date_of_birth"),
            tool_input.get("nationality"),
        )

    elif tool_name == "check_adverse_media":
        return check_adverse_media(
            tool_input["applicant_name"],
            tool_input.get("business_name")
        )

    elif tool_name == "calculate_risk_score":
        return calculate_risk_score(
            tool_input["extraction_result"],
            tool_input["sanctions_pep_result"],
            tool_input["adverse_media_result"]
        )
    elif tool_name == "extract_transactions":
        return extract_from_transactions(tool_input["csv_path"])

    elif tool_name == "score_alternative_credit":
        return score_alternative_credit(tool_input["metrics"])

    else:
        raise ValueError(f"Unknown tool requested: {tool_name}")


def run_kyc_case(user_request: str, max_turns: int = 10, related_case_id: str = None) -> str:
    """
    The agent loop. Sends the request + tools to Claude, executes any
    tool calls it makes, feeds results back, and repeats until Claude
    gives a final text answer (or we hit max_turns as a safety limit).
    """
    messages = [
        {"role": "user", "content": user_request}
    ]

    audit = AuditLog()
    print(f"\n=== Case ID: {audit.case_id} ===")

    for turn in range(max_turns):
        print(f"\n--- Turn {turn + 1} ---")

        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            tools=TOOLS,
            messages=messages,
        )

        # Always append Claude's response to the conversation history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            # Find the tool_use block(s) in this response
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    print(f"Claude is calling: {block.name}({block.input})")

                    result = execute_tool(block.name, block.input)
                    audit.record_tool_call(turn + 1, block.name, block.input, result)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            # Send all tool results back as one new "user" message
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            final_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            log_path = audit.finalize(final_text, related_case_id=related_case_id)
            print(f"Audit log saved: {log_path}")
            return final_text

        else:
            raise RuntimeError(f"Unexpected stop_reason: {response.stop_reason}")

    return "Reached max turns without a final answer — something may be looping."

def run_alternative_credit_case(csv_path: str, max_turns: int = 10) -> str:
    """
    Entry point for the Alternative Credit Scoring service. Same
    underlying loop as run_kyc_case, different task and toolset focus.
    """
    request = (
        f"Run an alternative credit readiness assessment on the bank "
        f"transaction data at '{csv_path}'. Use the available tools in "
        f"the correct order, then give me a final summary of the score, "
        f"band, and key findings."
    )
    return run_kyc_case(request)

if __name__ == "__main__":
    import sys as _sys

    file_path = _sys.argv[1] if len(_sys.argv) > 1 else "data/applicant_clean.txt"

    request = (
        f"Run a full KYC/AML risk assessment on the applicant document at "
        f"'{file_path}'. Use the available tools in the correct order, then "
        f"give me a final summary of the risk score, band, and key findings."
    )

    result = run_kyc_case(request)
    print("\n=== FINAL RESULT ===")
    print(result)