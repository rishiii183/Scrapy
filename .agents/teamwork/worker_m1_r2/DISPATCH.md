## 2026-10-23T23:24:15Z
You are worker_m1_r2, a Worker subagent in the Roofer Outreach Pipeline project.
Working directory: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m1_r2
Authoritative requirements file: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md
Project specification: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md
Explorer reports and patches:
- C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_1\handoff.md (and m1_fixes.patch)
- C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_2\handoff.md (and proposed_fixes.patch)
- C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_3\handoff.md

You MUST read C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md and C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md before starting work.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task is to apply the verified remediations across Milestone 1 files:
1. `src/scraper/filters.py`:
   - Make `clean_url_scheme` case-insensitive.
   - Unwrap outbound redirector URLs (e.g., `google.com/url?q=...`) to classify the destination URL.
2. `src/scraper/normalizer.py`:
   - Strip phone extensions before digit extraction (`r"(?i)\s*(?:ext(?:ension)?\.?|x|#)\s*:?\s*\d+"`).
   - Enforce NANP format: area code first digit [2-9], exchange code first digit [2-9]. Return "" for invalid / foreign numbers.
   - Add `pllc` to `entity_suffixes` in `normalize_business_name`.
3. `src/scraper/maps_extractor.py`:
   - In `parse_card_data`: Do not match phone area codes (e.g. `(903)`) as review counts when rating is absent.
4. `src/models.py`:
   - In `RawLead.dedup_key`: Call `get_dedup_key(self.cleaned_phone, self.business_name, self.state)`.
   - In `@field_validator("state")`: Enforce valid 50 US states + DC.
   - Add `@field_validator("cleaned_phone")`: Enforce 10-digit digits or empty string `""`.
5. `tests/unit/test_scraper.py`:
   - Update line 107 assertion for normalized dedup key (`apexroofers_TX`).

Execute and verify all test suites using `.\.venv\Scripts\python.exe`:
- `.\.venv\Scripts\python.exe -m pytest tests/unit/test_scraper.py`
- `.\.venv\Scripts\python.exe -m pytest tests/unit/test_adversarial_m1.py`
- `.\.venv\Scripts\python.exe -m pytest tests/test_m1_adversarial_stress.py`
- `.\.venv\Scripts\python.exe tests/run_all_tests.py`

Write your handoff report to `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m1_r2\handoff.md` and notify orchestrator.
