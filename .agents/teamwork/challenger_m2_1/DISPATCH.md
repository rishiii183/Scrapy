## 2026-10-23T23:52:07Z
You are challenger_m2_1, an Adversarial Challenger subagent for Milestone 2: Google Sheets CRM Ingestion & Deduplication.
Working directory: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\challenger_m2_1
Authoritative requirements file: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md
Project specification: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md

You MUST read C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md and C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md before starting work.

Challenger objectives:
1. Adversarially stress-test deduplication in src/crm/dedup.py:
   - Test company name variants: legal suffixes (LLC, Inc, Corp, PLLC, LLP, Ltd, Co), ampersand vs 'and', leading 'The', punctuation, casing, trailing conjunctions.
   - Test phone normalization: US standard, 11-digit with +1, extensions (ext 101, x4), punctuation variants, non-NANP invalid numbers.
   - Test cross-run deduplication and intra-batch duplicate detection.
   - Test idempotency: re-running ingestion with 100 duplicate leads against CRM index must result in exactly 0 unique ingested leads.
2. Write an empirical test script and run it via .\.venv\Scripts\python.exe.
3. Record your empirical results and explicit verdict: APPROVE or REQUEST_CHANGES in C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\challenger_m2_1\handoff.md and notify orchestrator.
