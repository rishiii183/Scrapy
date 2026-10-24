## 2026-10-24T00:00:57Z
You are worker_m2_r2, a Worker subagent in the Roofer Outreach Pipeline project.
Working directory: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m2_r2
Authoritative requirements file: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md
Project specification: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md
Challenger 1 handoff: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\challenger_m2_1\handoff.md

You MUST read C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md and C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md before starting work.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task is to resolve the Challenger 1 defect in Milestone 2:
1. In `src/crm/dedup.py`:
   Update `normalize_phone(phone: Optional[str]) -> str`:
   - Strip extension patterns (`ext 101`, `x4`, etc.) and enforce NANP format by delegating to `clean_phone_10digit(phone)` from `src.scraper.normalizer`.
   - Ensure that if `clean_phone_10digit` returns a valid 10-digit string, return it; otherwise return `""`.
2. Run test suites using .\.venv\Scripts\python.exe:
   - `.\.venv\Scripts\python.exe -m pytest tests/test_crm_adversarial_stress.py -v`
   - `.\.venv\Scripts\python.exe -m pytest tests/unit/test_crm.py -v`
   - `.\.venv\Scripts\python.exe -m pytest tests/unit/test_crm_adversarial.py -v`
   - `.\.venv\Scripts\python.exe tests/run_all_tests.py`
   - Full suite: `.\.venv\Scripts\python.exe -m pytest tests/`
3. Verify that all 65 tests in `test_crm_adversarial_stress.py` pass and all repository tests pass with zero regressions.
4. Write your handoff report to `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m2_r2\handoff.md` and notify orchestrator.
