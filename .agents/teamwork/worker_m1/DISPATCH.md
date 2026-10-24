## 2026-10-23T22:53:26Z
You are worker_m1, a Worker subagent in the Roofer Outreach Pipeline project.
Working directory: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m1
Authoritative requirements file: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md
Project specification: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md
Explorer survey handoff: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_survey_1\handoff.md

You MUST read C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md and C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md before starting work.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write ownership:
You exclusively own:
- src/models.py
- src/config.py
- src/scraper/
- tests/unit/test_scraper.py
Do NOT modify files owned by other milestones.

Your task is to implement Milestone 1: Google Maps Extraction Engine (Agent 1):
1. Create src/models.py defining Pydantic schemas for RawLead and QualifiedLead conforming to the interface contract in PROJECT.md.
2. Create src/config.py for system paths, Chrome executable path (%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe), and query settings.
3. Create src/scraper/browser_manager.py implementing Playwright browser lifecycle with anti-bot arguments.
4. Create src/scraper/filters.py implementing website filtering: strictly excluding custom domains (.com, .io, .net, .co, etc.) and capturing contractors with no website or social/directory profiles.
5. Create src/scraper/normalizer.py for 10-digit phone cleaning, address parsing / municipal centroid fallbacks, and trade specialty classification.
6. Create src/scraper/query_catalog.py with target metro queries across TX, FL, OH, GA, AZ.
7. Create src/scraper/maps_extractor.py orchestrating Google Maps searches, scrolling, parsing cards, and returning qualified leads.
8. Write comprehensive unit and extraction tests in tests/unit/test_scraper.py.
9. Execute tests using the project virtual environment (C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.venv\Scripts\python.exe). Verify all tests pass.
10. Write your handoff report to C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m1\handoff.md and message the orchestrator with commands and test output.
