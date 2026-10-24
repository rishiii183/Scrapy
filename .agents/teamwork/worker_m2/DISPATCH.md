## 2026-10-23T23:41:02Z
You are worker_m2, a Worker subagent in the Roofer Outreach Pipeline project.
Working directory: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m2
Authoritative requirements file: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md
Project specification: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md
Explorer 2 survey handoff: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_survey_2\handoff.md

You MUST read C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md and C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md before starting work.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write ownership:
You exclusively own:
- src/crm/
- tests/unit/test_crm.py
Do NOT modify files owned by other milestones.

Your task is to implement Milestone 2: Google Sheets CRM Ingestion & Deduplication (Agent 2):
1. Create `src/crm/sheets_client.py`:
   - Direct REST client using OAuth token at `C:\Users\rishi\.gemini\antigravity\plugin_data\gsheets\token.json` (`coderrishi183@gmail.com`) with automatic token refresh on HTTP 401 using refresh_token, client_id, client_secret.
   - Subprocess fallback to `C:\Users\rishi\.gemini\config\plugins\gsheets\skills\gsheets\scripts\gsheets.cmd`.
   - Support methods: `read_range(sheet_id, range_str)`, `append_rows(sheet_id, range_str, values)`, `update_range(sheet_id, range_str, values)`.
   - Provide clean mock/offline mode for unit testing without live network calls.
2. Create `src/crm/schema.py`:
   - 21-column schema definitions (Columns A through U):
     Lead Status, Priority, Company Name, Website, Industry / Niche, Company Size, Contact First Name, Contact Last Name, Job Title, Work Email, Email Verification, LinkedIn Profile, Location, Outreach Channel, Touch 1 Date, Last Follow-Up Date, Next Action Due, Personalized Icebreaker, Offer Angle / Pain Point, Est. Deal Value ($), Notes & Next Steps.
   - Converter from `QualifiedLead` to 21-element row list.
   - Strict validation: Priority must have emoji (`🔥 High`, `⚡ Medium`, `❄️ Low`), Deal Value must be unformatted integer (e.g. 4000), Company Size as `'1-10`.
3. Create `src/crm/lead_scorer.py`:
   - Priority scoring: review_count >= 10 without website -> `🔥 High` ($4,000); 3-9 reviews -> `⚡ Medium` ($3,500); <3 reviews -> `❄️ Low` ($3,000). Storm damage/commercial adjustments.
4. Create `src/crm/dedup.py`:
   - Parse existing CRM rows from `Leads Tracker!A2:U`.
   - Extract normalized names (via `normalize_business_name` from `src.scraper.normalizer`) and normalized phones (10 digits).
   - Deduplication engine comparing candidate leads against existing lookup sets and checking intra-batch duplicates.
5. Create `src/crm/ingestor.py`:
   - High-level ingestion workflow: reads CRM, deduplicates leads, scores priority/deal value, converts to row arrays, appends starting at row 14 (preserving formula ranges A2:T495), and returns structured summary.
6. Write unit tests in `tests/unit/test_crm.py` covering:
   - Schema mapping, formatting, and column alignment (Cols A-U)
   - Deduplication against existing CRM rows (and idempotency when re-running on same geographic data)
   - Lead scoring and priority assignment
   - Safe row appending starting at row 14 without formula corruption
   - Mock client and error handling
7. Execute tests using `.\.venv\Scripts\python.exe -m pytest tests/unit/test_crm.py -v`. Ensure 100% pass rate.
8. Also run `.\.venv\Scripts\python.exe tests/run_all_tests.py` to confirm zero regressions.
9. Write handoff report to `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m2\handoff.md` and notify orchestrator.
