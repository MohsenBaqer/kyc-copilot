"""
Tool schemas: descriptions the pilot tools, in the format Claude's
API expects for tool use.
"""

TOOLS = [
    {
        "name": "extract_document",
        "description": (
            "Extracts structured identity and business fields from a KYC "
            "intake document. Call this FIRST for any new applicant case, "
            "since every other tool needs the applicant's name and business "
            "name to work with."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the applicant's intake document, e.g. data/applicant_clean.txt"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "screen_sanctions_pep",
        "description": (
            "Checks an applicant's name and business name against sanctions "
            "and PEP (Politically Exposed Person) reference lists. Call this "
            "AFTER extract_document, using the applicant_name and business_name "
            "it returned."
        ),
       "input_schema": {
            "type": "object",
            "properties": {
                "applicant_name": {
                    "type": "string",
                    "description": "Full name of the applicant, from extract_document"
                },
                "business_name": {
                    "type": "string",
                    "description": "Business name, from extract_document"
                },
                "date_of_birth": {
                    "type": "string",
                    "description": "Applicant's date of birth, from extract_document. Improves match accuracy against the sanctions/PEP database."
                },
                "nationality": {
                    "type": "string",
                    "description": "Applicant's nationality, from extract_document. Improves match accuracy against the sanctions/PEP database."
                }
            },
            "required": ["applicant_name"]
        }
    },
    {
        "name": "check_adverse_media",
        "description": (
            "Checks an applicant's name and business name against a news/"
            "media dataset for negative coverage (fraud, regulatory action, "
            "criminal proceedings). Call this AFTER extract_document, in "
            "parallel with or after screen_sanctions_pep — order relative to "
            "sanctions screening doesn't matter, both need the same names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "applicant_name": {
                    "type": "string",
                    "description": "Full name of the applicant, from extract_document"
                },
                "business_name": {
                    "type": "string",
                    "description": "Business name, from extract_document"
                }
            },
            "required": ["applicant_name"]
        }
    },
    {
        "name": "calculate_risk_score",
        "description": (
            "Calculates the overall KYC/AML risk score for an applicant, combining "
            "results from extract_document, screen_sanctions_pep, and "
            "check_adverse_media. Call this LAST, only after all three of those "
            "have already run for this applicant."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "extraction_result": {
                    "type": "object",
                    "description": "The output object returned by extract_document for this applicant"
                },
                "sanctions_pep_result": {
                    "type": "object",
                    "description": "The output object returned by screen_sanctions_pep for this applicant"
                },
                "adverse_media_result": {
                    "type": "object",
                    "description": "The output object returned by check_adverse_media for this applicant"
                }
            },
            "required": ["extraction_result", "sanctions_pep_result", "adverse_media_result"]
        }
    },
        {
        "name": "extract_transactions",
        "description": (
            "Parses a bank transaction CSV into structured financial metrics "
            "(monthly revenue, expenses, cash flow, customer concentration, "
            "overdraft events). Call this FIRST when the user wants an "
            "alternative credit / financing readiness assessment, since "
            "score_alternative_credit needs its output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "csv_path": {
                    "type": "string",
                    "description": "Path to the bank transaction CSV file"
                }
            },
            "required": ["csv_path"]
        }
    },
    {
        "name": "score_alternative_credit",
        "description": (
            "Calculates a deterministic alternative credit readiness score "
            "from transaction metrics. Call this AFTER extract_transactions, "
            "using its output directly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metrics": {
                    "type": "object",
                    "description": "The output object returned by extract_transactions"
                }
            },
            "required": ["metrics"]
        }
    },
]
