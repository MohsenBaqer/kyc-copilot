"""
Audit logging: records every tool call and its result for a case,
plus the final summary, to a JSON file in logs/. 
"""

import json
import os
import uuid
from datetime import datetime, timezone

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)



class AuditLog:
    
    def _generate_case_id(self) -> str:
        date_prefix = datetime.now().strftime("%d%m%y")

        existing_numbers = []
        for filename in os.listdir(LOG_DIR):
            if filename.startswith(f"case_{date_prefix}-") and filename.endswith(".json"):
                # filename looks like: case_280826-3.json
                number_part = filename[len(f"case_{date_prefix}-"):-len(".json")]
                if number_part.isdigit():
                    existing_numbers.append(int(number_part))

        next_number = max(existing_numbers, default=0) + 1
        return f"{date_prefix}-{next_number}"
    
    def __init__(self):
        self.case_id = self._generate_case_id()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.tool_calls = []
        self.final_summary = None
        self.completed_at = None
        
    def record_tool_call(self, turn: int, tool_name: str, tool_input: dict, tool_output: dict):
        self.tool_calls.append({
            "turn": turn,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def finalize(self, final_summary: str, related_case_id: str = None):
        self.final_summary = final_summary
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.related_case_id = related_case_id
        return self._write()

    def _write(self):
        log_data = {
            "case_id": self.case_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "related_case_id": getattr(self, "related_case_id", None),
            "tool_calls": self.tool_calls,
            "final_summary": self.final_summary,
        }
        path = os.path.join(LOG_DIR, f"case_{self.case_id}.json")
        with open(path, "w") as f:
            json.dump(log_data, f, indent=2)
        return path
