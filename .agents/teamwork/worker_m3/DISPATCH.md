## 2026-10-24T15:07:29Z
You are worker_m3, a Worker subagent in the Roofer Outreach Pipeline project.
Working directory: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m3
Authoritative requirements file: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md
Project specification: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md
Explorer 3 survey handoff: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_survey_3\handoff.md

You MUST read C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md and C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md before starting work.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write ownership:
You exclusively own:
- src/personalizer/
- tests/unit/test_personalizer.py
Do NOT modify files owned by other milestones.

Your task is to implement Milestone 3: AI Personalization & Hook Generator (Agent 3):
1. Create `src/personalizer/prompts.py`:
   - System prompts and templates for bespoke 2-sentence icebreaker, revenue pain point, email subject, email body, and pre-formatted WhatsApp message.
   - Core invariants:
     * Sentence 1 references exact contractor city/metro and trade specialty.
     * Sentence 2 highlights revenue lost to local competitors ranking on Google Maps and organic search for emergency roof repairs.
2. Create `src/personalizer/template_engine.py`:
   - Deterministic Jinja2 engine with diverse templates providing natural variety while guaranteeing 100% adherence to acceptance criteria and 0 unparsed {{placeholders}}.
3. Create `src/personalizer/llm_engine.py`:
   - LLM adapter supporting OpenAI/Gemini/Anthropic with Pydantic JSON parsing when API keys are available, automatically falling back to `template_engine.py`.
4. Create `src/personalizer/generator.py`:
   - `PersonalizerGenerator.generate(lead) -> OutreachDraft`:
     * Generates icebreaker (Col R), offer angle / pain point (Col S).
     * Populates staging fields: Staged Email Subject (Col V), Staged Email Body (Col W), Pre-formatted WhatsApp Message (Col X), WhatsApp Click-to-Chat URL (`https://wa.me/1{phone}?text={encoded_msg}`) (Col Y), Outreach Approval Status (`Drafted / Ready for Review`) (Col Z).
     * Enforces strict validation: raises error if any placeholder tag like {{City}} or {{Name}} remains in output.
   - Batch generation: `generate_batch(leads) -> list[OutreachDraft]`.
   - Sheet staging helper: writes staging values to Google Sheets via `SheetsClient`.
5. Create `src/personalizer/__init__.py`: Clean exports.
6. Write unit tests in `tests/unit/test_personalizer.py` covering:
   - 100% of icebreakers mention contractor city and trade niche.
   - Emergency roof repairs competitor ranking revenue loss angle present.
   - Zero placeholder leakage assertion tests.
   - WhatsApp link construction with E.164 phone and URL-encoded message.
   - Staging columns mapping and `OutreachDraft` interface contract conformance.
7. Execute tests using `.\.venv\Scripts\python.exe -m pytest tests/unit/test_personalizer.py -v`. Ensure 100% pass rate.
8. Run full test suite: `.\.venv\Scripts\python.exe tests/run_all_tests.py` and `pytest tests/`.
9. Write handoff report to `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\worker_m3\handoff.md` and notify orchestrator.
