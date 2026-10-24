## 2026-10-24T15:54:12Z
Sender: ea620b15-fa32-4ce7-8b6f-715d76d0d59b
Priority: MESSAGE_PRIORITY_HIGH

You are worker_m4, a Worker subagent in the Roofer Outreach Pipeline project.
Working directory: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m4
Authoritative requirements file: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md
Project specification: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md
Explorer survey handoff: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_survey_3\handoff.md

You MUST read C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md and C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md before starting work.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write ownership:
You exclusively own:
- src/dispatcher/
- src/cli.py
- tests/unit/test_dispatcher.py
Do NOT modify files owned by other milestones.

Your task is to implement Milestone 4: Humanized Outreach Dispatch Engine with Staged Approval (Agent 4) & Unified CLI:
1. Create `src/dispatcher/safety_gate.py`:
   - Safety approval gate enforcing staged review mode.
   - Status defaults to `Drafted / Ready for Review` (Col Z).
   - `check_safety_gate(draft, confirmed: bool) -> bool`: returns True ONLY if user explicitly provides confirmation (`confirmed=True` via `--confirm` or user prompt).
   - Raises `SafetyGateError` or blocks dispatch if `confirmed` is False.
2. Create `src/dispatcher/email_client.py`:
   - SMTP Email client with live sending capability and dry-run simulator.
   - Dry-run simulator records dispatches, recipients, subjects, body copy, and timestamps in structured `DispatchResult`.
   - Handles connection errors and backoff gracefully.
3. Create `src/dispatcher/whatsapp_client.py`:
   - Fallback delivery channel for phone-only or email-bounced leads.
   - Generates and dispatches `wa.me` links (`https://wa.me/1{phone}?text={encoded_msg}`).
   - Dry-run simulator records WhatsApp clicks and payload.
4. Create `src/dispatcher/pacing.py`:
   - Randomized delay calculation within 45 to 180 seconds (`compute_random_delay(min_s=45, max_s=180)`).
   - Configurable delay parameter allowing sub-second delays during automated tests.
   - Daily send cap enforcement (`apply_daily_cap(drafts, cap=25)`).
   - Pacing tracker ensuring sender reputation safety.
5. Create `src/dispatcher/orchestrator.py` (`OutreachDispatcher`):
   - High-level dispatch runner coordinating approval check, pacing delay, channel execution, and CRM state updates.
   - Upon approved dispatch:
     * Column A (`Lead Status`): Transition from `Not Contacted` to `Contacted (Touch 1)`.
     * Column O (`Touch 1 Date`): Stamp current UTC date (`YYYY-MM-DD`).
     * Column U (`Notes & Next Steps`): Append `"Dispatched via <channel> on <date>."`.
     * Column Z (`Outreach Approval Status`): Transition from `Drafted / Ready for Review` to `Dispatched`.
     * Updates Google Sheet via `SheetsClient`.
6. Create `src/dispatcher/__init__.py`: Clean exports.
7. Create `src/cli.py`:
   - Unified command-line interface with subcommands:
     * `scrape`: Run Google Maps scraper.
     * `ingest`: Ingest leads into Google Sheets CRM.
     * `personalize`: Generate icebreakers and staged drafts.
     * `dispatch`: Run humanized outreach dispatcher (`--dry-run`, `--confirm`, `--cap`, `--channel`).
     * `pipeline`: Run end-to-end pipeline (scrape -> ingest -> personalize -> dispatch).
8. Write comprehensive unit tests in `tests/unit/test_dispatcher.py`:
   - Safety gate blocking unconfirmed drafts and allowing confirmed drafts.
   - Email simulator logging and dispatch verification.
   - WhatsApp fallback behavior.
   - Pacing delay boundaries (45-180s) and daily send cap enforcement.
   - CRM state transitions (Col A -> Contacted (Touch 1), Col O -> YYYY-MM-DD, Col Z -> Dispatched).
   - CLI subcommands invocation and argument handling.
9. Verify tests:
   - Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_dispatcher.py -v`.
   - Run: `.\.venv\Scripts\python.exe tests/run_all_tests.py` (confirm all 203 E2E tests pass).
   - Run: `.\.venv\Scripts\python.exe -m pytest tests/ -v` (full suite passes cleanly).
10. Write handoff report to `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m4\handoff.md`.
11. Notify orchestrator via send_message.
