# KYC SME Co-Pilot

A simple demo — built as a personal technical exercise.

Built manually against the raw Claude API, utilising tool-calling mechanics, conversation state, and agent orchestration end to end.

---

## What it does

**1. Onboard a New Customer (KYC/AML)**
Takes a freeform intake document or conversational input, extracts structured applicant data, screens it against real sanctions/PEP data and real adverse media, and produces a risk score with a full audit trail using a weighted calculation matrix.

**2. Check Financing Readiness (Alternative Credit Scoring)**
Takes raw bank transaction data (CSV) and produces a deterministic, explainable credit-readiness score based on cash-flow stability, revenue consistency, and related factors — an alternative to traditional credit bureau history.

Both services share one underlying agent architecture, one audit logging system, and one human-editable scoring configuration.

---

## Tech stack

Python · FastAPI · Anthropic Claude API · OpenSanctions API · NewsAPI.org · pandas ·  HTML/JS
