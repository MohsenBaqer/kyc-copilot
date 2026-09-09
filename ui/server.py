"""
FastAPI backend for the KYC/AML Co-Pilot browser UI.
Thin layer: receives requests, calls existing agent/tools logic,
returns results. No business logic lives here.
"""

import json
import os
import shutil
import sys

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse

sys.path.insert(0, ".")

from agent.harness import run_kyc_case
from tools.extract_document import extract_document, REQUIRED_FIELDS
from tools.lookup_public_info import lookup_public_info
from tools.extract_transactions import extract_from_transactions
from agent.harness import run_alternative_credit_case
CONFIG_PATH = "data/risk_rubric_config.json"



app = FastAPI()


@app.get("/api/config")
async def get_config():
    with open(CONFIG_PATH, "r") as f:
        return JSONResponse(json.load(f))


@app.post("/api/config")
async def update_config(config_json: str = Form(...)):
    try:
        parsed = json.loads(config_json)
    except json.JSONDecodeError as e:
        return JSONResponse({"error": f"Invalid JSON: {e}"}, status_code=400)

    with open(CONFIG_PATH, "w") as f:
        json.dump(parsed, f, indent=2)

    return JSONResponse({"success": True})
@app.get("/config", response_class=HTMLResponse)
async def serve_config():
    with open("ui/config.html", "r") as f:
        return f.read()
    
@app.post("/run-credit-case")
async def run_credit_case(file: UploadFile = File(...)):
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    result = run_alternative_credit_case(save_path)

    return JSONResponse({"result": result})

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

FIELD_LABELS = {
    "applicant_name": "the applicant's full name",
    "date_of_birth": "date of birth",
    "nationality": "nationality",
    "business_name": "business name",
    "business_registration_number": "business registration number",
    "business_address": "business address",
    "business_activity": "what the business does",
    "ownership": "ownership structure",
    "source_of_funds": "source of funds",
}

def find_existing_cases(name: str) -> list:
    matches = []
    if not os.path.isdir("logs"):
        return matches

    for filename in sorted(os.listdir("logs"), reverse=True):
        if not (filename.startswith("case_") and filename.endswith(".json")):
            continue
        with open(os.path.join("logs", filename), "r") as f:
            data = json.load(f)

        for call in data.get("tool_calls", []):
            if call.get("tool_name") == "extract_document":
                found_name = (call.get("tool_output") or {}).get("applicant_name")
                if found_name and found_name.strip().lower() == name.strip().lower():
                    matches.append({
                        "case_id": data.get("case_id"),
                        "started_at": data.get("started_at"),
                        "applicant_name": found_name,
                    })
                    break

    return matches

@app.get("/api/cases")
async def list_cases():
    cases = []
    for filename in sorted(os.listdir("logs"), reverse=True):
        if filename.startswith("case_") and filename.endswith(".json"):
            with open(os.path.join("logs", filename), "r") as f:
                data = json.load(f)
            cases.append({
                "case_id": data.get("case_id"),
                "started_at": data.get("started_at"),
                "completed_at": data.get("completed_at"),
                "final_summary": data.get("final_summary", ""),
            })
    return JSONResponse({"cases": cases})


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    path = os.path.join("logs", f"case_{case_id}.json")
    if not os.path.exists(path):
        return JSONResponse({"error": "Case not found"}, status_code=404)
    with open(path, "r") as f:
        data = json.load(f)
    return JSONResponse(data)

@app.post("/run-case")
async def run_case(file: UploadFile = File(...)):
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    request = (
        f"Run a full KYC/AML risk assessment on the applicant document at "
        f"'{save_path}'. Use the available tools in the correct order, then "
        f"give me a final summary of the risk score, band, and key findings."
    )

    result = run_kyc_case(request)

    return JSONResponse({"result": result})


@app.post("/run-case-text")
async def run_case_text(text: str = Form(...)):
    save_path = os.path.join(UPLOAD_DIR, "pasted_text_input.txt")
    with open(save_path, "w") as f:
        f.write(text)

    request = (
        f"Run a full KYC/AML risk assessment on the applicant document at "
        f"'{save_path}'. Use the available tools in the correct order, then "
        f"give me a final summary of the risk score, band, and key findings."
    )

    result = run_kyc_case(request)

    return JSONResponse({"result": result})


@app.post("/chat")
@app.post("/chat")
async def chat(accumulated_text: str = Form(...), duplicate_ack: str = Form("false"), related_case_id: str = Form("")):
    temp_path = os.path.join(UPLOAD_DIR, "chat_intake.txt")
    with open(temp_path, "w") as f:
        f.write(accumulated_text)

    extraction = extract_document(temp_path)
    missing = extraction["missing_fields"]

    # Duplicate check — only run once, before the user has acknowledged it
    if duplicate_ack != "true":
        name_to_check = extraction.get("applicant_name")
        if name_to_check:
            existing = find_existing_cases(name_to_check)
            if existing:
                return JSONResponse({
                    "complete": False,
                    "duplicate_found": True,
                    "message": f"I found an existing case for {name_to_check}.",
                    "existing_cases": existing,
                })

    if not missing:
        request = (
            f"Run a full KYC/AML risk assessment on the applicant document at "
            f"'{temp_path}'. Use the available tools in the correct order, then "
            f"give me a final summary of the risk score, band, and key findings."
        )
        result = run_kyc_case(request, related_case_id=related_case_id or None)
        return JSONResponse({"complete": True, "message": result})

    search_name = extraction.get("applicant_name") or extraction.get("business_name")
    suggestion = None
    if search_name:
        lookup_result = lookup_public_info(search_name)
        suggested = lookup_result.get("suggested_fields", {})
        relevant_suggestions = {
            field: value for field, value in suggested.items()
            if field in missing and value
        }
        if relevant_suggestions:
            suggestion = {
                "found_summary": lookup_result.get("found_summary"),
                "confidence_note": lookup_result.get("confidence_note"),
                "fields": relevant_suggestions,
            }

    missing_labels = [FIELD_LABELS.get(f, f) for f in missing]
    if len(missing_labels) == 1:
        ask = missing_labels[0]
    else:
        ask = ", ".join(missing_labels[:-1]) + " and " + missing_labels[-1]

    return JSONResponse({
        "complete": False,
        "message": f"Got it — I still need: {ask}.",
        "suggestion": suggestion,
    })
@app.post("/lookup")
async def lookup(name: str = Form(...)):
    result = lookup_public_info(name)
    return JSONResponse(result)
async def chat(accumulated_text: str = Form(...)):
    temp_path = os.path.join(UPLOAD_DIR, "chat_intake.txt")
    with open(temp_path, "w") as f:
        f.write(accumulated_text)

    extraction = extract_document(temp_path)
    missing = extraction["missing_fields"]

    if missing:
        missing_labels = [FIELD_LABELS.get(f, f) for f in missing]
        if len(missing_labels) == 1:
            ask = missing_labels[0]
        else:
            ask = ", ".join(missing_labels[:-1]) + " and " + missing_labels[-1]

        return JSONResponse({
            "complete": False,
            "message": f"Got it — I still need: {ask}. Could you share that?",
        })

    request = (
        f"Run a full KYC/AML risk assessment on the applicant document at "
        f"'{temp_path}'. Use the available tools in the correct order, then "
        f"give me a final summary of the risk score, band, and key findings."
    )
    result = run_kyc_case(request)

    return JSONResponse({
        "complete": True,
        "message": result,
    })

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    with open("ui/dashboard.html", "r") as f:
        return f.read()

@app.get("/", response_class=HTMLResponse)
async def serve_landing():
    with open("ui/landing.html", "r") as f:
        return f.read()


@app.get("/kyc", response_class=HTMLResponse)
async def serve_kyc():
    with open("ui/index.html", "r") as f:
        return f.read()


@app.get("/credit", response_class=HTMLResponse)
async def serve_credit():
    with open("ui/credit.html", "r") as f:
        return f.read()    
    
    